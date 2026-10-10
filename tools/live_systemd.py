"""Manual native systemd user-timer check on a disposable hosted Linux runner."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

if __package__:
    from .live_desktop_scheduler import NativeCheckError, observe
else:
    from live_desktop_scheduler import NativeCheckError, observe

ARGUMENTS = ['two words', 'quote"here', 'slash\\piece', '100%', '$HOME', '${USER}', '', ';', '--flag']


def inventory(folder):
    """Preserve user unit file bytes and enablement links, without following links."""
    result = {}
    for path in folder.rglob('*'):
        if path.is_symlink():
            result[str(path.relative_to(folder))] = ('link', os.readlink(path))
        elif path.is_file():
            result[str(path.relative_to(folder))] = ('file', path.read_bytes())
    return result


def exercise_units(read, keys, install, observe_run, remove):
    original = read()
    if any(key in original for key in keys):
        raise NativeCheckError('Probe units already exist; no changes made.')
    try:
        install()
        current = read()
        if not all(key in current for key in keys) or {k: v for k, v in current.items() if k not in keys} != original:
            raise NativeCheckError('Installation did not preserve unrelated user unit definitions.')
        observe_run()
    finally:
        if any(key in read() for key in keys):
            remove()
        if read() != original:
            raise NativeCheckError('User unit file/link inventory changed after cleanup.')
        print('Managed service/timer removed; unrelated user units preserved.', flush=True)


def main():
    if (sys.platform != 'linux' or os.environ.get('GITHUB_ACTIONS') != 'true'
            or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted'):
        print('Run only on a disposable GitHub-hosted Linux runner.', file=sys.stderr)
        return 1
    name = 'native_probe_' + uuid.uuid4().hex
    unit = 'uddnsupdater-' + name
    folder = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config') / 'systemd' / 'user'
    keys = [unit + '.service', unit + '.timer', 'timers.target.wants/' + unit + '.timer']
    try:
        with tempfile.TemporaryDirectory(prefix='uddns-native-systemd-') as directory:
            root = Path(directory).resolve()
            output = root / 'probe-output'
            output.mkdir(mode=0o700)
            target = datetime.now() + timedelta(minutes=2)
            config = root / 'schedule.ini'
            config.write_text(f'[SCHEDULE]\nhour={target.hour}\nminute={target.minute}\n', encoding='utf-8')
            started = datetime.now(timezone.utc)
            def schedule(operation):
                command = [sys.executable, '-m', 'UTaskScheduler.utask_scheduler',
                           '--config-file', str(config), '--scheduler', 'systemd', '--' + operation, name]
                if operation == 'install':
                    command += ['--', sys.executable, '-m', 'UTaskScheduler.execution_probe',
                                '--output-directory', str(output), '--'] + ARGUMENTS
                result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=90)
                if result.returncode:
                    print(result.stderr.strip(), file=sys.stderr)
                    raise NativeCheckError('Explicit systemd operation failed.')
            def scheduled_run():
                schedule('status')
                observe(output, sys.executable, started, arguments=ARGUMENTS)
                record = json.loads(next(output.glob('uddns-probe-*.json')).read_text(encoding='utf-8'))
                if not Path(record['working_directory']).samefile(Path.home()):
                    raise NativeCheckError('Systemd service did not use the configured home working directory.')
                print('Systemd literal percent, dollar, semicolon and empty arguments verified.', flush=True)
            exercise_units(lambda: inventory(folder), keys, lambda: schedule('install'), scheduled_run,
                           lambda: schedule('remove'))
        print('Native systemd user-timer integration passed.', flush=True)
        return 0
    except Exception as error:
        print('Native systemd check failed: ' + type(error).__name__ + '; inspect runner state.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
