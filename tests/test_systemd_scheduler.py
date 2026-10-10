import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
import pytest
from UTaskScheduler import utask_scheduler as app
from UTaskScheduler.schedulers import scheduler_systemd as renderer, systemd_install as native
from UTaskScheduler.schedulers import cron_install


def test_complete_daily_definition_preserves_literal_arguments():
    units = renderer.render_units('daily', ['/bin/echo', 'two words', 'quote"here', 'slash\\piece',
                                          '100%', '$HOME', '${USER}', '', ';'], [[0, 0], [23, 59]])
    service = units['uddnsupdater-daily.service']
    assert 'ExecStart=:"/bin/echo" "two words" "quote\\"here" "slash\\\\piece" "100%%" "$HOME" "${USER}" "" \\;\n' in service
    timer = units['uddnsupdater-daily.timer']
    assert 'OnCalendar=*-*-* 00:00:00\nOnCalendar=*-*-* 23:59:00\n' in timer
    assert 'Persistent=false' in timer and 'WantedBy=timers.target' in timer
    assert 'WorkingDirectory=%h' in service


@pytest.mark.parametrize('name', ['', '../x', 'a\nb', 'x'*65, 'ü'])
def test_invalid_names(name):
    with pytest.raises(renderer.SystemdError):
        renderer.render_units(name, ['/bin/echo'], [[0, 0]])


@pytest.mark.parametrize('command', [[], 'shell string', ['relative'], ['/bin/echo', '\n'],
                                    ['/bin/echo', '\t'], ['/bin/echo', '\ud800']])
def test_invalid_command(command):
    with pytest.raises(renderer.SystemdError):
        renderer.render_units('daily', command, [[0, 0]])


@pytest.mark.parametrize('intervals', [[], [[24, 0]], [[0, 60]], [[True, 0]], [[0]], [[0, 0], [0, 0]]])
def test_invalid_triggers(intervals):
    with pytest.raises(renderer.SystemdError):
        renderer.render_units('daily', ['/bin/echo'], intervals)


@pytest.mark.skipif(sys.platform != 'linux' or not shutil.which('systemd-analyze'), reason='Native systemd parser required')
def test_real_systemd_unit_parser_accepts_definitions(tmp_path):
    paths = []
    for filename, text in renderer.render_units('parser', ['/bin/echo', 'two words', '', ';', '100%',
                                                         '$HOME', 'quote"here', 'slash\\piece'], [[0, 0], [23, 59]]).items():
        path = tmp_path / filename
        path.write_text(text)
        paths.append(str(path))
    result = subprocess.run(['systemd-analyze', 'verify', *paths], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert not result.stderr


@pytest.fixture
def manager(tmp_path, monkeypatch):
    tmp_path = tmp_path.resolve()
    if not hasattr(native.os, 'getuid'):
        monkeypatch.setattr(native.os, 'getuid', lambda: 0, raising=False)
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    folder = tmp_path / 'systemd' / 'user'
    calls = []
    state = {'enabled': False, 'active': False, 'fail': None}
    def run(argv, **kwargs):
        assert argv[:3] == ['systemctl', '--user', '--no-pager']
        assert kwargs['timeout'] == 30 and 'shell' not in kwargs
        calls.append(argv[3:])
        operation = argv[3]
        if state['fail'] == operation:
            return SimpleNamespace(returncode=1, stdout='', stderr='PRIVATE DIAGNOSTIC')
        if operation == 'show':
            filename = argv[-1]
            path = folder / filename
            loaded = path.exists()
            values = {'LoadState': 'loaded' if loaded else 'not-found',
                      'FragmentPath': str(path) if loaded else '', 'DropInPaths': '',
                      'ActiveState': 'active' if filename.endswith('.timer') and state['active'] else 'inactive',
                      'UnitFileState': 'enabled' if filename.endswith('.timer') and state['enabled'] else 'static' if loaded else ''}
            return SimpleNamespace(returncode=0 if loaded else 4,
                                   stdout=''.join(k+'='+v+'\n' for k, v in values.items()), stderr='')
        if operation == 'enable':
            state.update(enabled=True, active=True)
            wants = folder / 'timers.target.wants'
            wants.mkdir()
            (wants / argv[-1]).symlink_to(folder / argv[-1])
        if operation == 'disable':
            state.update(enabled=False, active=False)
            link = folder / 'timers.target.wants' / argv[-1]
            if link.is_symlink():
                link.unlink()
        if operation == 'stop' and argv[-1].endswith('.timer'):
            state['active'] = False
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    monkeypatch.setattr(native.subprocess, 'run', run)
    return folder, calls, state


def test_install_status_remove_preserves_unrelated_units(manager):
    folder, calls, state = manager
    folder.mkdir(parents=True)
    unrelated = folder / 'unrelated.service'
    unrelated.write_text('unrelated definition')
    native.install('daily', ['/bin/echo', 'two words'], [[12, 0]])
    assert state['active'] and state['enabled']
    assert native.status('daily')['timer']['ActiveState'] == 'active'
    if sys.platform != 'win32':
        assert (folder / 'uddnsupdater-daily.service').stat().st_mode & 0o777 == 0o600
    native.remove('daily')
    assert not list(folder.glob('uddnsupdater-*'))
    assert unrelated.read_text() == 'unrelated definition'
    disable = next(i for i, c in enumerate(calls) if c[0] == 'disable')
    stop_service = next(i for i, c in enumerate(calls) if c[0] == 'stop' and c[-1].endswith('.service'))
    assert disable < stop_service


def test_reinstall_refused_without_native_mutation(manager):
    _, calls, _ = manager
    native.install('daily', ['/bin/echo'], [[0, 0]])
    calls.clear()
    with pytest.raises(renderer.SystemdError, match='exists'):
        native.install('daily', ['/bin/echo'], [[0, 0]])
    assert not calls


def test_native_failure_retains_recoverable_definitions(manager):
    folder, _, state = manager
    state['fail'] = 'enable'
    with pytest.raises(renderer.SystemdError):
        native.install('daily', ['/bin/echo'], [[0, 0]])
    assert len(native.managed_files('daily')[1]) == 2
    state['fail'] = None
    native.remove('daily')
    assert not list(folder.glob('uddnsupdater-*'))


def test_partial_file_creation_can_be_removed(manager):
    folder, _, _ = manager
    folder.mkdir(parents=True)
    units = renderer.render_units('daily', ['/bin/echo'], [[0, 0]])
    (folder / 'uddnsupdater-daily.service').write_text(units['uddnsupdater-daily.service'])
    native.remove('daily')
    assert not list(folder.glob('uddnsupdater-*'))


@pytest.mark.parametrize('tamper', ['foreign', 'changed', 'dropin', 'different-metadata'])
def test_foreign_changed_and_dropin_units_never_removed(manager, tamper):
    folder, calls, _ = manager
    native.install('daily', ['/bin/echo'], [[0, 0]])
    path = folder / 'uddnsupdater-daily.service'
    if tamper == 'foreign':
        path.write_text('foreign unit')
    elif tamper == 'changed':
        path.write_text(path.read_text() + 'Restart=always\n')
    elif tamper == 'different-metadata':
        path.write_text(renderer.render_units('daily', ['/bin/true'], [[0, 0]])[path.name])
    else:
        (folder / (path.name + '.d')).mkdir()
    calls.clear()
    with pytest.raises(renderer.SystemdError):
        native.remove('daily')
    assert path.exists() and not calls


def test_native_identity_and_dropins_fail_closed(manager, monkeypatch):
    folder, _, _ = manager
    original = native.unit_state
    def foreign(unit):
        return dict(original(unit), LoadState='loaded', FragmentPath='/etc/systemd/user/'+unit)
    monkeypatch.setattr(native, 'unit_state', foreign)
    with pytest.raises(renderer.SystemdError, match='identity'):
        native.install('daily', ['/bin/echo'], [[0, 0]])
    assert not folder.exists()


def test_native_manager_unavailable_before_files_created(manager):
    folder, _, state = manager
    state['fail'] = 'show'
    with pytest.raises(renderer.SystemdError) as error:
        native.install('daily', ['/bin/echo'], [[0, 0]])
    assert 'PRIVATE' not in str(error.value) and not folder.exists()


@pytest.mark.parametrize('output', ['', 'LoadState=not-found\n', 'LoadState=not-found\nLoadState=loaded\n'])
def test_incomplete_or_duplicate_native_properties_refused(monkeypatch, output):
    monkeypatch.setattr(native, 'native', lambda *a, **k: SimpleNamespace(returncode=4, stdout=output))
    with pytest.raises(renderer.SystemdError):
        native.unit_state('uddnsupdater-daily.timer')


def test_failed_native_removal_retains_definitions(manager):
    folder, _, state = manager
    native.install('daily', ['/bin/echo'], [[0, 0]])
    state['fail'] = 'disable'
    with pytest.raises(renderer.SystemdError):
        native.remove('daily')
    assert len(native.managed_files('daily')[1]) == 2
    assert (folder / 'uddnsupdater-daily.timer').exists()


def test_relative_config_home_refused(monkeypatch):
    monkeypatch.setenv('XDG_CONFIG_HOME', 'relative')
    with pytest.raises(renderer.SystemdError):
        native.location('daily')


@pytest.mark.skipif(sys.platform == 'win32', reason='POSIX symlink/ownership policy')
def test_symlink_parent_refused(tmp_path, monkeypatch):
    folder = tmp_path / 'actual'
    folder.mkdir()
    alias = tmp_path / 'alias'
    alias.symlink_to(folder, target_is_directory=True)
    monkeypatch.setenv('XDG_CONFIG_HOME', str(alias))
    with pytest.raises(renderer.SystemdError):
        native.location('daily')


@pytest.mark.skipif(sys.platform == 'win32', reason='POSIX symlink policy')
def test_symlink_enablement_directory_refused(manager, tmp_path):
    folder, calls, _ = manager
    folder.mkdir(parents=True)
    (folder / 'timers.target.wants').symlink_to(tmp_path / 'missing', target_is_directory=True)
    with pytest.raises(renderer.SystemdError):
        native.install('daily', ['/bin/echo'], [[0, 0]])
    assert not calls


def test_linux_cli_backend_choice_and_existing_modes(manager, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(app.sys, 'platform', 'linux')
    config = tmp_path / 'schedule.ini'
    config.write_text('[SCHEDULE]\nhour=*/6\nminute=*/15\n')
    prefix = ['--config-file', str(config)]
    assert app.main(prefix + ['--scheduler', 'systemd', '--preview', 'daily', '--', '/bin/echo', '$HOME']) == 0
    output = capsys.readouterr().out
    assert output.count('OnCalendar=') == 16 and 'ExecStart=' in output
    assert app.main(prefix + ['--scheduler', 'systemd', '--install', 'daily', '--', '/bin/echo']) == 0
    assert app.main(['--scheduler', 'systemd', '--status', 'daily']) == 0
    assert app.main(['--scheduler', 'systemd', '--remove', 'daily']) == 0
    assert app.main(prefix + ['--scheduler', 'cron', '--preview', 'daily', '--', '/bin/echo']) == 0
    assert app.main(prefix + ['--preview-cron', '--', '/bin/echo']) == 0
    monkeypatch.setattr(app.sys, 'platform', 'darwin')
    assert app.main(['--remove-systemd', 'daily']) == 2


def test_preview_is_readonly_and_invalid_schedule_has_no_native_calls(manager, tmp_path, monkeypatch):
    folder, calls, _ = manager
    monkeypatch.setattr(app.sys, 'platform', 'linux')
    config = tmp_path / 'schedule.ini'
    config.write_text('[SCHEDULE]\nhour=12\nminute=0\n')
    assert app.main(['--config-file', str(config), '--preview-systemd', 'daily', '--', '/bin/echo']) == 0
    assert not calls and not folder.exists()
    config.write_text('[SCHEDULE]\nhour=invalid\n')
    assert app.main(['--config-file', str(config), '--install-systemd', 'daily', '--', '/bin/echo']) == 2
    assert not calls and not folder.exists()
    assert app.main(['--remove-systemd', 'daily', '--', '/bin/echo']) == 2


@pytest.mark.parametrize('args', [['--scheduler', 'systemd'], ['--install', 'daily'],
                                 ['--scheduler', 'cron', '--preview-systemd', 'daily']])
def test_backend_selection_requires_generic_mode(args):
    with pytest.raises(SystemExit) as error:
        app.main(args)
    assert error.value.code == 2


def test_cron_status_only_reads_validated_markers(monkeypatch):
    calls = []
    text = cron_install.replace_block('unrelated\n', 'daily', 'SHELL=/bin/sh\n0 0 * * * /bin/true\n')
    def read(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout=text, stderr='')
    monkeypatch.setattr(cron_install.subprocess, 'run', read)
    assert cron_install.status('daily')
    assert not cron_install.status('other')
    assert calls == [['crontab', '-l'], ['crontab', '-l']]
