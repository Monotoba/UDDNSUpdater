"""Manual native cron execution check on a disposable GitHub-hosted Linux runner."""
from datetime import datetime, timedelta
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

SENTINEL = '# Unrelated native-test entry\n0 0 31 2 * /bin/true\n'
ARGUMENTS = ['two words', 'quote"here', '100%', 'slash\\%piece', '', '--flag']
NAME = 'native_execution_probe'
BEGIN = '# BEGIN UDDNSUpdater ' + NAME


class NativeCheckError(RuntimeError):
    pass


def verify_record(record, executable, home):
    if (record.get('schema_version') != 1 or record.get('arguments') != ARGUMENTS
            or Path(record.get('executable', '')).resolve() != Path(executable).resolve()
            or not Path(record.get('working_directory', '')).samefile(home)):
        raise NativeCheckError('Scheduled probe context or arguments did not match.')
    stamp = datetime.fromisoformat(record['timestamp_utc'])
    if stamp.tzinfo is None:
        raise NativeCheckError('Scheduled probe timestamp is missing its timezone.')


def exercise(read, write, delete, install, uninstall, observe):
    """Preserve native state, including after a partially failed installation."""
    original = read()
    if original not in (None, ''):
        raise NativeCheckError('This check requires an empty disposable user crontab.')
    try:
        write(SENTINEL)
        install()
        registered = read()
        if not registered or not registered.startswith(SENTINEL) or BEGIN not in registered:
            raise NativeCheckError('Registration did not preserve the unrelated entry.')
        observe()
        uninstall()
        if read() != SENTINEL:
            raise NativeCheckError('Named removal did not preserve the unrelated entry.')
        print('Native registration, scheduled execution, and named removal passed.', flush=True)
    finally:
        if original is None:
            delete()
        else:
            write(original)
        if read() != original:
            raise NativeCheckError('Original crontab restoration failed.')
        print('Original disposable-runner crontab restored.', flush=True)


def main():
    if (sys.platform != 'linux' or os.environ.get('GITHUB_ACTIONS') != 'true'
            or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted'):
        print('Run only on a disposable GitHub-hosted Linux runner.', file=sys.stderr)
        return 1
    environment = dict(os.environ, LC_ALL='C')
    def command(arguments, input=None):
        result = subprocess.run(arguments, input=input, capture_output=True,
                                text=True, timeout=20, env=environment)
        return result
    def read():
        result = command(['crontab', '-l'])
        if result.returncode == 0:
            return result.stdout
        if result.returncode == 1 and result.stderr.strip() == 'no crontab for ' + getpass.getuser():
            return None
        raise NativeCheckError('Cannot read native crontab.')
    def write(text):
        if command(['crontab', '-'], input=text).returncode:
            raise NativeCheckError('Cannot write native crontab.')
    def delete():
        result = command(['crontab', '-r'])
        if result.returncode and read() is not None:
            raise NativeCheckError('Cannot remove temporary crontab.')
    try:
        with tempfile.TemporaryDirectory(prefix='uddns-native-cron-') as directory:
            root = Path(directory).resolve()
            os.chmod(root, 0o700)
            output = root/'probe-output'
            output.mkdir(mode=0o700)
            config = root/'schedule.ini'
            target = datetime.now() + timedelta(minutes=2)
            config.write_text(f'[SCHEDULE]\nhour={target.hour}\nminute={target.minute}\n')
            # Both scheduler and probe resolve from the installed wheel outside checkout.
            def schedule(mode):
                arguments = [sys.executable, '-m', 'UTaskScheduler.utask_scheduler',
                             '--config-file', str(config), mode, NAME]
                if mode == '--install-cron':
                    arguments += ['--', sys.executable, '-m', 'UTaskScheduler.execution_probe',
                                  '--output-directory', str(output), '--'] + ARGUMENTS
                result = subprocess.run(arguments, cwd=root, env=environment,
                                        capture_output=True, text=True, timeout=30)
                if result.returncode:
                    raise NativeCheckError('Explicit scheduler operation failed.')
            def observe():
                deadline = time.monotonic() + 180
                while time.monotonic() < deadline:
                    records = list(output.glob('uddns-probe-*.json'))
                    if records:
                        if len(records) != 1:
                            raise NativeCheckError('Expected exactly one scheduled probe run.')
                        record = json.loads(records[0].read_text(encoding='utf-8'))
                        verify_record(record, sys.executable, Path.home())
                        print('Actual cron execution verified:', record['timestamp_utc'], flush=True)
                        return
                    time.sleep(2)
                raise NativeCheckError('No scheduled execution observed within three minutes.')
            exercise(read, write, delete, lambda: schedule('--install-cron'),
                     lambda: schedule('--remove-cron'), observe)
        return 0
    except Exception:
        print('Native cron check failed; inspect phases and runner state.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
