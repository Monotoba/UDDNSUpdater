"""Explicit current-user launchd registration; no automatic invocation."""
import os
from pathlib import Path
import plistlib
import re
import subprocess

from .scheduler_macos import LaunchdPreviewError, MacTaskScheduler


def task_label(name):
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', name):
        raise LaunchdPreviewError('Task name must use 1–64 letters, digits, underscores or hyphens.')
    return 'org.monotoba.uddnsupdater.'+name


def native(argv):
    try:
        return subprocess.run(['/bin/launchctl']+argv, capture_output=True,
                              text=True, timeout=15)
    except (OSError, subprocess.SubprocessError, UnicodeError):
        raise LaunchdPreviewError('Launchd operation failed; inspect native state before retrying.') from None


def registered(domain, label):
    result = native(['print', domain+'/'+label])
    if result.returncode == 0:
        return True
    if result.returncode == 113:  # launchctl: service not found
        return False
    raise LaunchdPreviewError('Cannot determine launchd registration state; no further changes made.')


def location(name):
    label = task_label(name)
    folder = Path.home()/'Library'/'LaunchAgents'
    if any(path.is_symlink() for path in (Path.home(), Path.home()/'Library', folder)):
        raise LaunchdPreviewError('LaunchAgents must use a trusted directory without symlinks.')
    return label, folder/(label+'.plist'), f'gui/{os.getuid()}'


def install(name, command, intervals):
    label, path, domain = location(name)
    if not isinstance(intervals, (list, tuple)) or not intervals:
        raise LaunchdPreviewError('Daily trigger times are required.')
    definition = MacTaskScheduler(intervals[0], command=command, label=label).render_plist(intervals=intervals)
    if path.exists() or path.is_symlink():
        raise LaunchdPreviewError('Task file already exists; remove it explicitly before reinstalling.')
    if registered(domain, label):
        raise LaunchdPreviewError('Task label is already registered; no changes made.')
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Exclusive creation prevents overwriting an unrelated existing file.
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            handle.write(definition)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        raise LaunchdPreviewError('Cannot write task definition; inspect the task file before retrying.') from None
    if native(['bootstrap', domain, str(path)]).returncode:
        raise LaunchdPreviewError('Launchd registration failed; definition retained for explicit recovery.')
    if not registered(domain, label):
        raise LaunchdPreviewError('Launchd verification failed; inspect native state before retrying.')
    return path


def remove(name):
    label, path, domain = location(name)
    if path.is_symlink():
        raise LaunchdPreviewError('Refusing a symlink task definition.')
    if not path.exists():
        raise LaunchdPreviewError('Task definition is missing; no native changes made.')
    try:
        if path.stat().st_size > 262144:
            raise ValueError
        definition = plistlib.loads(path.read_bytes())
        if set(definition) != {'Label', 'ProgramArguments', 'StartCalendarInterval'} or definition['Label'] != label:
            raise ValueError
        intervals = [[item['Hour'], item['Minute']] for item in definition['StartCalendarInterval']]
        MacTaskScheduler(intervals[0], command=definition['ProgramArguments'], label=label).render_plist(intervals=intervals)
    except (OSError, ValueError, TypeError, KeyError, IndexError, plistlib.InvalidFileException):
        raise LaunchdPreviewError('Task definition is not a valid managed daily task; no changes made.') from None
    loaded = registered(domain, label)
    if loaded and native(['bootout', domain+'/'+label]).returncode:
        raise LaunchdPreviewError('Launchd removal failed; definition retained.')
    # launchctl print must no longer find the label before deleting its definition.
    if registered(domain, label):
        raise LaunchdPreviewError('Task is still registered; definition retained.')
    try:
        path.unlink()
    except OSError:
        raise LaunchdPreviewError('Task stopped but definition removal failed; inspect the task file.') from None
