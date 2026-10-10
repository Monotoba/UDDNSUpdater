import json
from types import SimpleNamespace
import subprocess
import pytest
from UTaskScheduler.schedulers import windows_install as windows
from UTaskScheduler.schedulers.scheduler_windows import WindowsPreviewError
from UTaskScheduler import utask_scheduler as app

@pytest.fixture
def native(monkeypatch):
    monkeypatch.setenv('SystemRoot', r'C:\Windows')
    calls = []
    control = {'status':0, 'transform':lambda xml:xml}
    def run(argv, **kwargs):
        assert argv[0] == r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
        assert kwargs['timeout'] == 30 and 'shell' not in kwargs
        payload = json.loads(kwargs['input'])
        calls.append(payload)
        text = json.dumps({'ok':True, 'xml':control['transform'](payload['xml'])})
        return SimpleNamespace(returncode=control['status'], stdout=text, stderr='SECRET')
    monkeypatch.setattr(windows.subprocess, 'run', run)
    return calls, control


def test_register_definition_and_remove(native):
    calls, _ = native
    windows.install('daily', [r'C:\Python\python.exe', 'space argument'], [[0,0],[12,30]], '2026-10-10')
    assert 'InteractiveToken' in calls[0]['xml'] and 'LeastPrivilege' in calls[0]['xml']
    assert calls[0]['name'] == 'UDDNSUpdater-daily'
    windows.remove('daily')
    assert calls[1]['operation'] == 'remove'
    assert '-Force' not in windows.SCRIPT and 'Principal.UserId -ne $sid' in windows.SCRIPT

@pytest.mark.parametrize('name', ['', '../x', 'a\nb', 'x'*65])
def test_invalid_name_before_native(native, name):
    calls, _ = native
    with pytest.raises(WindowsPreviewError):
        windows.remove(name)
    assert not calls

@pytest.mark.parametrize('status', [1, 5])
def test_native_failure_sanitized(native, status):
    _, control = native
    control['status'] = status
    with pytest.raises(WindowsPreviewError) as error:
        windows.remove('daily')
    assert 'SECRET' not in str(error.value)

@pytest.mark.parametrize('old,new', [('LeastPrivilege','HighestAvailable'), ('InteractiveToken','Password'), ('space argument','wrong'), ('T00:00:00','T01:00:00')])
def test_export_mismatch_reported(native, old, new):
    _, control = native
    control['transform'] = lambda xml: xml.replace(old,new)
    with pytest.raises(WindowsPreviewError):
        windows.install('daily',[r'C:\Python\python.exe','space argument'],[[0,0]],'2026-10-10')

def test_invalid_schedule_before_native(native):
    calls, _ = native
    with pytest.raises(WindowsPreviewError):
        windows.install('daily',[r'C:\Python\python.exe'],[[0,0]],None)
    assert not calls

def test_timeout_sanitized(native, monkeypatch):
    def fail(*a, **k):
        raise subprocess.TimeoutExpired('SECRET',30)
    monkeypatch.setattr(windows.subprocess,'run',fail)
    with pytest.raises(WindowsPreviewError) as error:
        windows.remove('daily')
    assert 'SECRET' not in str(error.value)

def test_cli_modes(native, tmp_path, monkeypatch):
    monkeypatch.setattr(app.sys,'platform','win32')
    config = tmp_path/'schedule.ini'
    config.write_text('[SCHEDULE]\nHour=0\nMinute=0\n')
    assert app.main(['--config-file',str(config),'--install-windows','daily','--start-date','2026-10-10','--',r'C:\Python\python.exe']) == 0
    assert app.main(['--remove-windows','daily']) == 0
    monkeypatch.setattr(app.sys,'platform','linux')
    assert app.main(['--remove-windows','daily']) == 2


@pytest.mark.skipif(__import__('sys').platform != 'win32', reason='Windows PowerShell parser required')
def test_powershell_script_parses_without_native_registration():
    import os
    from pathlib import PureWindowsPath
    executable = str(PureWindowsPath(os.environ['SystemRoot'])/'System32'/'WindowsPowerShell'/'v1.0'/'powershell.exe')
    code = "$tokens=$null; $errors=$null; [System.Management.Automation.Language.Parser]::ParseInput([Console]::In.ReadToEnd(),[ref]$tokens,[ref]$errors) | Out-Null; if ($errors.Count) { exit 1 }"
    result = subprocess.run([executable,'-NoProfile','-NonInteractive','-Command',code],
                            input=windows.SCRIPT,capture_output=True,text=True,timeout=30)
    assert result.returncode == 0
