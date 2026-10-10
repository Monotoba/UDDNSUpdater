from pathlib import Path
import plistlib
from types import SimpleNamespace
import subprocess
import pytest
from UTaskScheduler.schedulers import launchd_install as launchd
from UTaskScheduler.schedulers.scheduler_macos import LaunchdPreviewError
from UTaskScheduler import utask_scheduler as app

@pytest.fixture
def system(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setattr(launchd.os, 'getuid', lambda: 123, raising=False)
    control = {'loaded': False, 'bootstrap': 0, 'bootout': 0}
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        assert argv[0] == '/bin/launchctl' and kwargs['timeout'] == 15 and 'shell' not in kwargs
        if argv[1] == 'print':
            status = 0 if control['loaded'] else 113
        else:
            status = control[argv[1]]
            if status == 0:
                control['loaded'] = argv[1] == 'bootstrap'
        return SimpleNamespace(returncode=status, stdout='SECRET', stderr='SECRET')
    monkeypatch.setattr(launchd.subprocess, 'run', run)
    return tmp_path, control, calls

def test_install_remove_preserves_other_files(system):
    root, control, calls = system
    folder = root/'Library'/'LaunchAgents'
    folder.mkdir(parents=True)
    other = folder/'other.plist'
    other.write_text('keep')
    path = launchd.install('daily', ['/usr/bin/python3', 'space argument'], [[0,0],[12,30]])
    data = plistlib.loads(path.read_bytes())
    assert data['ProgramArguments'] == ['/usr/bin/python3', 'space argument']
    assert data['StartCalendarInterval'] == [{'Hour':0,'Minute':0},{'Hour':12,'Minute':30}]
    assert control['loaded']
    launchd.remove('daily')
    assert not control['loaded'] and not path.exists() and other.read_text() == 'keep'

@pytest.mark.parametrize('name', ['', '../evil', 'x\ny', 'x'*65])
def test_invalid_name_before_native(system, name):
    _, _, calls = system
    with pytest.raises(LaunchdPreviewError):
        launchd.install(name, ['/usr/bin/true'], [[0,0]])
    assert not calls

def test_existing_file_never_overwritten(system):
    root, _, calls = system
    path = root/'Library'/'LaunchAgents'/'org.monotoba.uddnsupdater.daily.plist'
    path.parent.mkdir(parents=True)
    path.write_text('keep')
    with pytest.raises(LaunchdPreviewError):
        launchd.install('daily', ['/usr/bin/true'], [[0,0]])
    assert not calls and path.read_text() == 'keep'

def test_registered_label_collision(system):
    root, control, _ = system
    control['loaded'] = True
    with pytest.raises(LaunchdPreviewError):
        launchd.install('daily', ['/usr/bin/true'], [[0,0]])
    assert not (root/'Library').exists()

def test_registration_failure_retains_definition(system):
    root, control, _ = system
    control['bootstrap'] = 1
    with pytest.raises(LaunchdPreviewError) as error:
        launchd.install('daily', ['/usr/bin/true'], [[0,0]])
    assert 'SECRET' not in str(error.value)
    assert list((root/'Library'/'LaunchAgents').glob('*.plist'))
    launchd.remove('daily')
    assert not list((root/'Library'/'LaunchAgents').glob('*.plist'))

def test_removal_failure_retains_definition(system):
    _, control, _ = system
    path = launchd.install('daily', ['/usr/bin/true'], [[0,0]])
    control['bootout'] = 1
    with pytest.raises(LaunchdPreviewError):
        launchd.remove('daily')
    assert path.exists() and control['loaded']

def test_timeout_sanitized(system, monkeypatch):
    def fail(*a, **k):
        raise subprocess.TimeoutExpired('SECRET', 15)
    monkeypatch.setattr(launchd.subprocess, 'run', fail)
    with pytest.raises(LaunchdPreviewError) as error:
        launchd.install('daily', ['/usr/bin/true'], [[0,0]])
    assert 'SECRET' not in str(error.value)

def test_symlink_directory_rejected(system):
    root, _, calls = system
    (root/'real').mkdir()
    try:
        (root/'Library').symlink_to(root/'real', target_is_directory=True)
    except OSError:
        pytest.skip('Symlink unavailable')
    with pytest.raises(LaunchdPreviewError):
        launchd.install('daily', ['/usr/bin/true'], [[0,0]])
    assert not calls

def test_missing_or_foreign_definition_not_removed(system):
    root, _, calls = system
    with pytest.raises(LaunchdPreviewError):
        launchd.remove('daily')
    folder = root/'Library'/'LaunchAgents'
    folder.mkdir(parents=True)
    path = folder/'org.monotoba.uddnsupdater.daily.plist'
    path.write_bytes(plistlib.dumps({'Label':'other'}))
    with pytest.raises(LaunchdPreviewError):
        launchd.remove('daily')
    assert path.exists() and not calls

def test_cli_explicit_mode(system, tmp_path, monkeypatch):
    monkeypatch.setattr(app.sys, 'platform', 'darwin')
    config = tmp_path/'schedule.ini'
    config.write_text('[SCHEDULE]\nHour=0\nMinute=0\n')
    assert app.main(['--config-file',str(config),'--install-launchd','daily','--','/usr/bin/true']) == 0
    assert app.main(['--remove-launchd','daily']) == 0
    monkeypatch.setattr(app.sys, 'platform', 'linux')
    assert app.main(['--remove-launchd','daily']) == 2


def test_unknown_registration_status_fails_closed(system, monkeypatch):
    root, _, _ = system
    monkeypatch.setattr(launchd.subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=5))
    with pytest.raises(LaunchdPreviewError):
        launchd.install('daily', ['/usr/bin/true'], [[0,0]])
    assert not (root/'Library').exists()
