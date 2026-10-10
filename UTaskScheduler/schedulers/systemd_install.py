"""Explicit, current-user systemd timer lifecycle with managed-file checks."""
import json
import os
from pathlib import Path
import stat
import subprocess

from .scheduler_systemd import MARKER, METADATA, SystemdError, render_units, task_name


def location(name):
    task_name(name)
    base = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    if not base.is_absolute():
        raise SystemdError('XDG_CONFIG_HOME must be absolute.')
    folder = base / 'systemd' / 'user'
    if any(p.is_symlink() for p in (folder, *folder.parents)):
        raise SystemdError('User unit directories must have trusted nonsymlink parents.')
    if (folder / 'timers.target.wants').is_symlink():
        raise SystemdError('Timer enablement directory must not be a symlink.')
    return folder


def native(arguments, *, show=False):
    try:
        result = subprocess.run(['systemctl', '--user', '--no-pager', *arguments],
                                capture_output=True, text=True, timeout=30,
                                env=dict(os.environ, LC_ALL='C'))
        if result.returncode not in ((0, 4) if show else (0,)):
            raise SystemdError('User systemd operation failed; inspect native state before retrying.')
        return result
    except (OSError, subprocess.SubprocessError, UnicodeError):
        raise SystemdError('Cannot contact the user systemd manager; inspect your login session.') from None


def unit_state(unit):
    result = native(['show', '--all', '--property=LoadState', '--property=FragmentPath',
                     '--property=DropInPaths', '--property=ActiveState', '--property=UnitFileState', unit], show=True)
    values = {}
    for line in result.stdout.splitlines():
        key, separator, value = line.partition('=')
        if not separator or key in values:
            raise SystemdError('Cannot determine user unit state.')
        values[key] = value
    if set(values) != {'LoadState', 'FragmentPath', 'DropInPaths', 'ActiveState', 'UnitFileState'}:
        raise SystemdError('Cannot determine user unit state.')
    if result.returncode and values['LoadState'] != 'not-found':
        raise SystemdError('Cannot determine user unit state.')
    return values


def check_native(unit, path, *, allow_missing=False):
    state = unit_state(unit)
    if (allow_missing and state['LoadState'] == 'not-found' and not state['FragmentPath']
            and not state['DropInPaths'] and state['ActiveState'] == 'inactive'):
        return state
    if (state['LoadState'] != 'loaded' or state['FragmentPath'] != str(path)
            or state['DropInPaths']):
        raise SystemdError('Unit identity or drop-ins do not match the managed definition.')
    return state


def managed_files(name):
    folder = location(name)
    unit = task_name(name)
    files = {}
    metadata = None
    for suffix in ('.service', '.timer'):
        path = folder / (unit + suffix)
        dropin = folder / (path.name + '.d')
        if path.is_symlink() or dropin.exists() or dropin.is_symlink():
            raise SystemdError('Symlink definitions and user drop-ins are not managed tasks.')
        if not path.exists():
            continue
        try:
            info = path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > 524288:
                raise ValueError
            text = path.read_text(encoding='utf-8')
            lines = text.splitlines()
            if len(lines) < 2 or lines[0] != MARKER or not lines[1].startswith(METADATA):
                raise ValueError
            definition = json.loads(lines[1][len(METADATA):])
            if (set(definition) != {'name', 'command', 'intervals'} or definition['name'] != name
                    or (metadata is not None and metadata != definition)):
                raise ValueError
            expected = render_units(name, definition['command'], definition['intervals'])
            if text != expected[path.name]:
                raise ValueError
            metadata = definition
            files[path.name] = path
        except (OSError, UnicodeError, ValueError, TypeError, KeyError):
            raise SystemdError('Definition is not an unchanged, current-user managed unit.') from None
    if not files:
        raise SystemdError('Managed unit files are missing; no changes made.')
    link = folder / 'timers.target.wants' / (unit + '.timer')
    if link.exists() or link.is_symlink():
        try:
            valid = link.is_symlink() and link.resolve() == folder / (unit + '.timer')
        except (OSError, RuntimeError):
            valid = False
        if not valid:
            raise SystemdError('Timer enablement link is not managed.')
    return folder, files


def install(name, command, intervals):
    definitions = render_units(name, command, intervals)
    folder = location(name)
    for unit in definitions:
        path = folder / unit
        dropin = folder / (unit + '.d')
        if path.exists() or path.is_symlink() or dropin.exists() or dropin.is_symlink():
            raise SystemdError('Task definition exists; remove explicitly before reinstalling.')
        state = check_native(unit, path, allow_missing=True)
        if state['LoadState'] != 'not-found':
            raise SystemdError('Unit name is already registered; no changes made.')
    timer = task_name(name) + '.timer'
    link = folder / 'timers.target.wants' / timer
    if link.exists() or link.is_symlink():
        raise SystemdError('Timer enablement link already exists; no changes made.')
    try:
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        for unit, text in definitions.items():
            descriptor = os.open(folder / unit, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
    except OSError:
        raise SystemdError('Cannot write units; partial definitions retained for explicit recovery.') from None
    native(['daemon-reload'])
    for unit in definitions:
        check_native(unit, folder / unit)
    native(['enable', '--now', timer])
    state = check_native(timer, folder / timer)
    if state['ActiveState'] != 'active' or state['UnitFileState'] != 'enabled':
        raise SystemdError('Timer activation verification failed; inspect user units.')
    managed_files(name)


def status(name):
    folder, files = managed_files(name)
    unit = task_name(name)
    return {suffix[1:]: check_native(unit + suffix, folder / (unit + suffix), allow_missing=True)
            for suffix in ('.service', '.timer')}


def remove(name):
    folder, files = managed_files(name)
    unit = task_name(name)
    states = {suffix: check_native(unit + suffix, folder / (unit + suffix), allow_missing=True)
              for suffix in ('.timer', '.service')}
    # Stop future triggers before stopping any running instance of this service.
    if states['.timer']['LoadState'] != 'not-found':
        native(['disable', '--now', unit + '.timer'])
    for suffix, state in states.items():
        if state['LoadState'] != 'not-found':
            native(['stop', unit + suffix])
            if unit_state(unit + suffix)['ActiveState'] != 'inactive':
                raise SystemdError('Unit is still active; definitions retained.')
    # Revalidate after native actions and before deleting definitions.
    _, current = managed_files(name)
    if current != files:
        raise SystemdError('Managed file inventory changed during removal.')
    link = folder / 'timers.target.wants' / (unit + '.timer')
    if link.exists() or link.is_symlink():
        raise SystemdError('Timer is still enabled; definitions retained.')
    try:
        for path in files.values():
            path.unlink()
    except OSError:
        raise SystemdError('Unit files partially removed; inspect user units.') from None
    native(['daemon-reload'])
    for suffix in states:
        if check_native(unit + suffix, folder / (unit + suffix), allow_missing=True)['LoadState'] != 'not-found':
            raise SystemdError('Unit remains registered after file removal.')
