"""Manual scheduled-execution check on disposable Windows/macOS hosted runners."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path, PureWindowsPath
import subprocess
import sys
import tempfile
import time
import uuid

ARGUMENTS = ['two words', 'quote"here', 'slash\\piece', '', '--flag']


class NativeCheckError(RuntimeError):
    pass


def exercise(inventory, key, install, observe, remove):
    """Remove partial registrations and verify unrelated definitions are preserved."""
    original = inventory()
    if key in original:
        raise NativeCheckError('Probe task already exists; no changes made.')
    try:
        install()
        current = inventory()
        if key not in current or {k: v for k, v in current.items() if k != key} != original:
            raise NativeCheckError('Registration did not preserve unrelated tasks.')
        observe()
    finally:
        # Inventory is authoritative; never remove a pre-existing colliding task.
        if key in inventory():
            remove()
        if inventory() != original:
            raise NativeCheckError('Native cleanup did not restore the original task inventory.')
        print('Probe removed; unrelated task definitions preserved.', flush=True)


def verify_record(record, executable, started, arguments=ARGUMENTS):
    if (record.get('schema_version') != 1 or record.get('arguments') != arguments
            or Path(record.get('executable', '')).resolve() != Path(executable).resolve()):
        raise NativeCheckError('Scheduled probe executable or arguments did not match.')
    stamp = datetime.fromisoformat(record['timestamp_utc'])
    if stamp.tzinfo is None or stamp < started:
        raise NativeCheckError('Scheduled probe timestamp is invalid.')
    if not Path(record.get('working_directory', '')).is_absolute():
        raise NativeCheckError('Scheduled working directory is not absolute.')


def observe(output, executable, started, *, arguments=ARGUMENTS, clock=time.monotonic, sleep=time.sleep):
    deadline = clock() + 180
    while clock() < deadline:
        records = list(output.glob('uddns-probe-*.json'))
        if records:
            if len(records) != 1:
                raise NativeCheckError('Expected exactly one scheduled execution.')
            # The probe creates its file before writing; retry an incomplete write.
            try:
                record = json.loads(records[0].read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                sleep(1)
                continue
            verify_record(record, executable, started, arguments)
            print('Actual scheduled execution verified:', record['timestamp_utc'], flush=True)
            print('Scheduled working directory:', record['working_directory'], flush=True)
            return
        sleep(2)
    raise NativeCheckError('No scheduled execution observed within three minutes.')


WINDOWS_INVENTORY = r'''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$items = @{}
Get-ScheduledTask -TaskPath '\' -ErrorAction Stop | ForEach-Object {
    $items[$_.TaskName] = Export-ScheduledTask -TaskName $_.TaskName -TaskPath '\' -ErrorAction Stop
}
ConvertTo-Json -InputObject $items -Compress
'''


def main():
    if (sys.platform not in ('win32', 'darwin') or os.environ.get('GITHUB_ACTIONS') != 'true'
            or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted'):
        print('Run only on a disposable GitHub-hosted Windows/macOS runner.', file=sys.stderr)
        return 1
    name = 'native_probe_' + uuid.uuid4().hex
    mode = 'windows' if sys.platform == 'win32' else 'launchd'
    key = 'UDDNSUpdater-' + name if mode == 'windows' else 'org.monotoba.uddnsupdater.' + name + '.plist'
    phase = 'inventory'
    try:
        if mode == 'windows':
            powershell = str(PureWindowsPath(os.environ['SystemRoot']) / 'System32' /
                             'WindowsPowerShell' / 'v1.0' / 'powershell.exe')
            def inventory():
                result = subprocess.run([powershell, '-NoProfile', '-NonInteractive', '-Command',
                                         WINDOWS_INVENTORY], capture_output=True, text=True,
                                        encoding='utf-8', timeout=30, check=True)
                value = json.loads(result.stdout.lstrip('\ufeff'))
                if not isinstance(value, dict):
                    raise NativeCheckError('Invalid task inventory.')
                return value
        else:
            # The public backend intentionally supports a GUI user domain only.
            subprocess.run(['/bin/launchctl', 'print', f'gui/{os.getuid()}'],
                           capture_output=True, timeout=20, check=True)
            folder = Path.home() / 'Library' / 'LaunchAgents'
            def inventory():
                return {p.name: p.read_bytes() for p in folder.glob('*.plist')}
        with tempfile.TemporaryDirectory(prefix='uddns-native-desktop-') as directory:
            root = Path(directory).resolve()
            output = root / 'probe-output'
            output.mkdir(mode=0o700)
            target = datetime.now() + timedelta(minutes=2)
            config = root / 'schedule.ini'
            config.write_text(f'[SCHEDULE]\nhour={target.hour}\nminute={target.minute}\n', encoding='utf-8')
            started = datetime.now(timezone.utc)
            def schedule(operation):
                nonlocal phase
                phase = operation
                command = [sys.executable, '-m', 'UTaskScheduler.utask_scheduler',
                           '--config-file', str(config), '--' + operation + '-' + mode, name]
                if operation == 'install':
                    if mode == 'windows':
                        command += ['--start-date', target.date().isoformat()]
                    command += ['--', sys.executable, '-m', 'UTaskScheduler.execution_probe',
                                '--output-directory', str(output), '--'] + ARGUMENTS
                result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=45)
                if result.returncode:
                    # These fixed CLI messages contain no credentials or task inventory.
                    print(result.stderr.strip(), file=sys.stderr)
                    raise NativeCheckError('Explicit scheduler operation failed.')
            def scheduled_run():
                nonlocal phase
                phase = 'scheduled execution'
                observe(output, sys.executable, started)
            exercise(inventory, key, lambda: schedule('install'), scheduled_run,
                     lambda: schedule('remove'))
            if mode == 'launchd':
                # CLI removal already checks launchctl absence before unlinking.
                print('GUI-domain launchd registration and removal verified.', flush=True)
        print('Native desktop scheduler integration passed.', flush=True)
        return 0
    except Exception as error:
        print(f'Native check failed during {phase}: {type(error).__name__}. Inspect runner state.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
