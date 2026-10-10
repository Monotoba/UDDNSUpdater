"""Generate named systemd user service/timer definitions without native actions."""
import json
from pathlib import PurePosixPath
import re

MARKER = '# UDDNSUpdater managed systemd user task v1'
METADATA = '# Definition: '


class SystemdError(ValueError):
    """Controlled user-timer definition or registration error."""


def task_name(name):
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', name):
        raise SystemdError('Task name must use 1–64 letters, digits, underscores or hyphens.')
    return 'uddnsupdater-' + name


def quote_argument(argument):
    # The : ExecStart prefix disables $ expansion; %% escapes unit specifiers.
    # C-style escaping and whole-word quotes are systemd syntax, not shell syntax.
    if argument == ';':
        return r'\;'
    return '"' + argument.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'


def render_units(name, command, intervals):
    unit = task_name(name)
    if (not isinstance(command, (list, tuple)) or not command
            or any(not isinstance(arg, str) or any(ord(c) < 32 or ord(c) == 127
                   or 0xD800 <= ord(c) <= 0xDFFF for c in arg) for arg in command)
            or not PurePosixPath(command[0]).is_absolute()):
        raise SystemdError('Systemd requires an absolute executable and UTF-8 arguments without control characters.')
    if not isinstance(intervals, (list, tuple)) or not 1 <= len(intervals) <= 1440:
        raise SystemdError('Systemd requires 1 to 1440 daily triggers.')
    for item in intervals:
        if (not isinstance(item, (list, tuple)) or len(item) != 2
                or any(type(v) is not int for v in item)
                or not 0 <= item[0] < 24 or not 0 <= item[1] < 60):
            raise SystemdError('Invalid systemd daily trigger time.')
    times = [list(item) for item in intervals]
    if len({tuple(item) for item in times}) != len(times):
        raise SystemdError('Duplicate systemd trigger times are not supported.')
    argv = ' '.join(quote_argument(arg) for arg in command)
    if len(argv.encode('utf-8')) > 65536:
        raise SystemdError('Systemd command is too long.')
    metadata = json.dumps({'name': name, 'command': list(command), 'intervals': times},
                          ensure_ascii=True, separators=(',', ':'))
    header = MARKER + '\n' + METADATA + metadata + '\n'
    service = (header + '[Unit]\nDescription=UDDNSUpdater named user task\n\n'
               '[Service]\nType=oneshot\nWorkingDirectory=%h\nUMask=0077\n'
               'ExecStart=:' + argv + '\n')
    timer = (header + '[Unit]\nDescription=UDDNSUpdater named user timer\n\n[Timer]\n'
             + ''.join(f'OnCalendar=*-*-* {h:02d}:{m:02d}:00\n' for h, m in times)
             + 'AccuracySec=1s\nRandomizedDelaySec=0\nPersistent=false\nUnit=' + unit
             + '.service\n\n[Install]\nWantedBy=timers.target\n')
    return {unit + '.service': service, unit + '.timer': timer}
