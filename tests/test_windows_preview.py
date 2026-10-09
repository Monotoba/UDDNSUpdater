import json
import os
import subprocess
import sys
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pytest
from UTaskScheduler import utask_scheduler as app
from UTaskScheduler.schedulers.scheduler_windows import WindowsTaskScheduler, WindowsPreviewError, NAMESPACE

NS = {'t': NAMESPACE}
ARGS = ['', 'space here', 'a"b', 'trail slash \\', '<&>', '$HOME', 'a&b', 'a|b', '`echo x`', 'café']


@pytest.fixture(autouse=True)
def no_native(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail('Native execution attempted')
    monkeypatch.setattr(os, 'system', blocked)
    monkeypatch.setattr(subprocess, 'run', blocked)


def render(command=None, **kwargs):
    return WindowsTaskScheduler([23, 59], command or ['C:\\Python\\python.exe']).create_task_xml(start_date='2026-10-09', **kwargs)


def test_structure():
    root = ET.fromstring(render(['C:\\Program Files\\python.exe', *ARGS]))
    assert root.tag == '{' + NAMESPACE + '}Task'
    assert root.findtext('t:Triggers/t:CalendarTrigger/t:StartBoundary', namespaces=NS) == '2026-10-09T23:59:00'
    assert root.findtext('t:Triggers/t:CalendarTrigger/t:ScheduleByDay/t:DaysInterval', namespaces=NS) == '1'
    assert root.find('t:Triggers/t:CalendarTrigger/t:Repetition', NS) is None
    assert root.findtext('t:Actions/t:Exec/t:Command', namespaces=NS) == 'C:\\Program Files\\python.exe'
    assert root.findtext('t:Actions/t:Exec/t:Arguments', namespaces=NS) == subprocess.list2cmdline(ARGS)


@pytest.mark.parametrize('command', [[], None, 'C:\\python.exe', ['python.exe'], ['C:python.exe'],
                                    ['\\python.exe'], ['C:\\job.cmd'], ['C:\\job.bat'],
                                    ['C:\\python.exe', '%HOME%'], ['C:\\python.exe', '100%'],
                                    ['C:\\python.exe', '\x01'], ['C:\\python.exe', '\ud800'],
                                    ['C:\\python.exe', '\n'], ['C:\\python.exe', 1]])
def test_bad_command(command):
    with pytest.raises(WindowsPreviewError):
        WindowsTaskScheduler([0, 0], command).create_task_xml(start_date='2026-10-09')


@pytest.mark.parametrize('start', [None, '', '2026-1-1', '2026-02-30', '0000-01-01', '2026-10-09T00:00:00', 1])
def test_bad_date(start):
    with pytest.raises(WindowsPreviewError):
        WindowsTaskScheduler([0, 0], ['C:\\python.exe']).create_task_xml(start_date=start)


@pytest.mark.parametrize('times', [[], [[0, 0]] * 49, [[24, 0]], [[0, 60]], [[True, 0]], [[0]], [[0, 0], [-1, 0]]])
def test_bad_times(times):
    with pytest.raises(WindowsPreviewError):
        render(intervals=times)


def test_trigger_limit():
    root = ET.fromstring(render(intervals=[[h, m] for h in range(24) for m in [0, 30]]))
    assert len(root.find('t:Triggers', NS)) == 48


@pytest.mark.parametrize('name', ['', '../bad', 'a:b', '\x00', None])
def test_bad_name(name):
    with pytest.raises(WindowsPreviewError):
        WindowsTaskScheduler([0, 0], ['C:\\python.exe'], task_name=name).create_task_xml(start_date='2026-10-09')


def test_install_blocked():
    with pytest.raises(WindowsPreviewError):
        WindowsTaskScheduler([0, 0], ['C:\\python.exe']).schedule()


def test_cli(tmp_path, monkeypatch, capsys):
    config = tmp_path / 'schedule.ini'
    config.write_text('[SCHEDULE]\nHour=*/6\nMinute=*/15\n', encoding='utf-8')
    monkeypatch.setattr(app, 'sys', SimpleNamespace(platform='win32', stderr=app.sys.stderr))
    assert app.main(['--config-file', str(config), '--preview-windows', '--start-date', '2026-10-09', '--', 'C:\\python.exe', 'a&b']) == 0
    output = capsys.readouterr()
    root = ET.fromstring(output.out)
    boundaries = [x.text for x in root.findall('t:Triggers/t:CalendarTrigger/t:StartBoundary', NS)]
    assert boundaries == [f'2026-10-09T{h:02d}:{m:02d}:00' for h in range(0, 24, 6) for m in range(0, 60, 15)]
    assert output.err == ''


@pytest.mark.parametrize('platform,minute', [('linux', '0'), ('win32', '*')])
def test_cli_failure(tmp_path, monkeypatch, capsys, platform, minute):
    config = tmp_path / 'schedule.ini'
    config.write_text(f'[SCHEDULE]\nHour=*\nMinute={minute}\n', encoding='utf-8')
    monkeypatch.setattr(app, 'sys', SimpleNamespace(platform=platform, stderr=app.sys.stderr))
    assert app.main(['--config-file', str(config), '--preview-windows', '--start-date', '2026-10-09', '--', 'C:\\python.exe', 'SECRET']) == 2
    output = capsys.readouterr()
    assert output.out == '' and 'SECRET' not in output.err


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows process argument parsing required')
def test_actual_windows_argv(monkeypatch):
    monkeypatch.undo()
    command = [sys.executable, '-c', 'import json,sys;print(json.dumps(sys.argv[1:]))', *ARGS]
    root = ET.fromstring(render(command))
    exe = root.findtext('t:Actions/t:Exec/t:Command', namespaces=NS)
    arguments = root.findtext('t:Actions/t:Exec/t:Arguments', namespaces=NS)
    result = subprocess.run(subprocess.list2cmdline([exe]) + ' ' + arguments,
                            executable=exe, shell=False, capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == ARGS
