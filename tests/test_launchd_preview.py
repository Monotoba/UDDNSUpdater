import os
import plistlib
import subprocess
from types import SimpleNamespace

import pytest

from UTaskScheduler import utask_scheduler as app
from UTaskScheduler.schedulers.scheduler_macos import MacTaskScheduler, LaunchdPreviewError


@pytest.fixture(autouse=True)
def no_native(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail('Native execution attempted')
    monkeypatch.setattr(os, 'system', blocked)
    monkeypatch.setattr(subprocess, 'run', blocked)


def test_literal_arguments():
    args = ['/path with spaces/python', '', '<tag>&"', "a'b", '$(echo unsafe)',
            '`echo unsafe`', '$HOME', '*', '100%', 'a\\b', 'café', 'a\tb']
    data = plistlib.loads(MacTaskScheduler([23, 59], command=args).render_plist().encode())
    assert data == {'Label': 'org.monotoba.uddnsupdater', 'ProgramArguments': args,
                    'StartCalendarInterval': [{'Hour': 23, 'Minute': 59}]}


@pytest.mark.parametrize('command', [None, [], 'python job.py', ['relative'], [True],
                                    ['/bin/python', 1], ['/bin/python', '\x00'],
                                    ['/bin/python', '\n'], ['/bin/python', '\r'],
                                    ['/bin/python', '\x01'], ['/bin/python', '\ud800'],
                                    ['/bin/python', '\ufffe']])
def test_bad_command(command):
    with pytest.raises(LaunchdPreviewError):
        MacTaskScheduler([0, 0], command=command).render_plist()


@pytest.mark.parametrize('time', [None, [], [0], [0, 0, 0], [True, 0], [-1, 0],
                                 [24, 0], [0, 60], [0, -1], ['0', 0]])
def test_bad_time(time):
    with pytest.raises(LaunchdPreviewError):
        MacTaskScheduler(time, command=['/bin/python']).render_plist()


@pytest.mark.parametrize('label', ['', '../file', 'a b', 'a\n', None, 'x' * 201])
def test_bad_label(label):
    with pytest.raises(LaunchdPreviewError):
        MacTaskScheduler([0, 0], command=['/bin/python'], label=label).render_plist()


@pytest.mark.parametrize('method,args', [('schedule', ()), ('create_user_task', ('x', 'x')),
                                       ('create_system_task', ('x', 'x')),
                                       ('write_plist_file', ('x', 'x', 'x'))])
def test_install_blocked(method, args, tmp_path):
    scheduler = MacTaskScheduler([0, 0], command=['/bin/python'])
    with pytest.raises(LaunchdPreviewError):
        getattr(scheduler, method)(*args)
    assert list(tmp_path.iterdir()) == []


def test_system_blocked():
    with pytest.raises(LaunchdPreviewError):
        MacTaskScheduler([0, 0], True, command=['/bin/python']).render_plist()


def test_dry_run():
    scheduler = MacTaskScheduler([0, 0], command=['/bin/python'])
    assert scheduler.schedule(dry_run=True) == scheduler.render_plist()


def test_all_triggers_and_cli(tmp_path, monkeypatch, capsys):
    config = tmp_path / 'schedule.ini'
    config.write_text('[SCHEDULE]\nHour=*/6\nMinute=*/15\n', encoding='utf-8')
    monkeypatch.setattr(app, 'sys', SimpleNamespace(platform='darwin', stderr=app.sys.stderr))
    argv = ['--config-file', str(config), '--preview-launchd', '--', '/bin/python', 'job &.py']
    assert app.main(argv) == 0
    output = capsys.readouterr()
    data = plistlib.loads(output.out.encode())
    assert output.err == ''
    assert data['ProgramArguments'] == ['/bin/python', 'job &.py']
    assert data['StartCalendarInterval'] == [{'Hour': h, 'Minute': m}
                                           for h in range(0, 24, 6) for m in range(0, 60, 15)]


@pytest.mark.parametrize('platform,command', [('linux', ['/bin/python']),
                                              ('darwin', ['relative']),
                                              ('darwin', ['/bin/python', '\x01SECRET'])])
def test_cli_errors_no_partial_output(tmp_path, monkeypatch, capsys, platform, command):
    config = tmp_path / 'schedule.ini'
    config.write_text('[SCHEDULE]\n', encoding='utf-8')
    monkeypatch.setattr(app, 'sys', SimpleNamespace(platform=platform, stderr=app.sys.stderr))
    assert app.main(['--config-file', str(config), '--preview-launchd', '--', *command]) == 2
    output = capsys.readouterr()
    assert output.out == ''
    assert 'SECRET' not in output.err


def test_modes_exclusive():
    with pytest.raises(SystemExit) as error:
        app.main(['--preview-launchd', '--dry-run', '--', '/bin/python'])
    assert error.value.code == 2


def test_invalid_late_interval():
    with pytest.raises(LaunchdPreviewError):
        MacTaskScheduler([0, 0], command=['/bin/python']).render_plist(intervals=[[0, 0], [24, 0]])


@pytest.mark.skipif(__import__('sys').platform != 'darwin', reason='Apple plutil requires macOS')
def test_apple_plutil_accepts_definition(tmp_path, monkeypatch):
    monkeypatch.undo()
    path = tmp_path / 'preview.plist'
    path.write_text(MacTaskScheduler([23, 59], command=['/bin/echo', '<& café']).render_plist(),
                    encoding='utf-8')
    result = subprocess.run(['/usr/bin/plutil', '-lint', str(path)],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
