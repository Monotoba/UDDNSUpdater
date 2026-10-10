"""Explicit, named Linux user-crontab installation; no automatic invocation."""
import re
import subprocess

from .scheduler_unix import CronPreviewError


def markers(name):
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', name):
        raise CronPreviewError('Task name must use 1–64 letters, digits, underscores or hyphens.')
    return f'# BEGIN UDDNSUpdater {name}', f'# END UDDNSUpdater {name}'


def replace_block(existing, name, preview=None):
    begin, end = markers(name)
    lines = existing.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.rstrip('\r\n') == begin]
    ends = [i for i, line in enumerate(lines) if line.rstrip('\r\n') == end]
    if len(starts) != len(ends) or len(starts) > 1 or (starts and starts[0] >= ends[0]):
        raise CronPreviewError('Managed crontab markers are inconsistent; no changes made.')
    if starts:
        del lines[starts[0]:ends[0]+1]
    retained = ''.join(lines)
    if preview is None:
        return retained
    if not preview.startswith('SHELL=/bin/sh\n') or not preview.endswith('\n'):
        raise CronPreviewError('Invalid cron definition; no changes made.')
    # Append our block and restore the last effective shell for future entries.
    shell = '/bin/sh'
    for line in retained.splitlines():
        match = re.match(r'^\s*SHELL\s*=\s*(.*?)\s*$', line)
        if match:
            shell = match.group(1)
    if not re.fullmatch(r'/[A-Za-z0-9_./-]+', shell):
        raise CronPreviewError('Cannot safely preserve the existing cron shell setting.')
    separator = '' if not retained or retained.endswith('\n') else '\n'
    return retained+separator+begin+'\n'+preview+f'SHELL={shell}\n'+end+'\n'


def apply(name, preview=None):
    markers(name)  # Validate before reading or writing native state.
    try:
        current = subprocess.run(['crontab', '-l'], capture_output=True, text=True,
                                 timeout=15, env=None)
        if current.returncode != 0:
            # Locale-independent absence detection is not reliable. Fail closed;
            # the user can initialize an empty crontab separately.
            raise CronPreviewError('Cannot read existing user crontab; initialize it before installation.')
        updated = replace_block(current.stdout, name, preview)
        if updated == current.stdout:
            return False
        written = subprocess.run(['crontab', '-'], input=updated, capture_output=True,
                                 text=True, timeout=15)
        if written.returncode:
            raise CronPreviewError('Crontab installation failed; verify native state before retrying.')
        verified = subprocess.run(['crontab', '-l'], capture_output=True, text=True, timeout=15)
        if verified.returncode or verified.stdout != updated:
            raise CronPreviewError('Crontab verification failed; verify native state before retrying.')
        return True
    except (OSError, subprocess.SubprocessError, UnicodeError):
        raise CronPreviewError('Cannot complete crontab operation; verify native state before retrying.') from None
