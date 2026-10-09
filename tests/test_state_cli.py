import json
from pathlib import Path
import pytest
import requests
import ddns_updater as app
import update_state

IP = '192.0.2.1'
SECRET = 'secret%credential'


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    def blocked(*args, **kwargs):
        pytest.fail('Live HTTP prohibited')
    monkeypatch.setattr(requests.sessions.Session, 'request', blocked)
    calls = []
    controls = {'ip': IP, 'result': True, 'time': 100, 'fail': None}
    class Fake:
        required_fields = ('password',)
        def __init__(self, name, settings):
            calls.append(('discover', name))
            self.name = name
            if controls['fail'] == 'init':
                raise RuntimeError(SECRET)
            self.external_ip = controls['ip']
        def update_ddns(self):
            calls.append(('update', self.name))
            if controls['fail'] == self.name:
                raise RuntimeError(SECRET)
            return controls['result']
    monkeypatch.setattr(app, 'load_provider_classes', lambda: {'Fake': Fake})
    monkeypatch.setattr(app.time, 'time', lambda: controls['time'])
    config = tmp_path / 'config.ini'
    config.write_text(f'[first]\nddns_provider=Fake\npassword={SECRET}\n', encoding='utf-8')
    state = tmp_path / 'state.json'
    args = ['--config-file', str(config), '--no-log', '--state-file', str(state), '--refresh-seconds', '10']
    return config, state, args, calls, controls, Fake


def test_accept_skip_change_expire(setup, capsys):
    config, state, args, calls, controls, _ = setup
    assert app.main(args) == 0
    original = state.read_bytes()
    assert SECRET not in original.decode()
    calls.clear()
    controls['time'] = 109
    assert app.main(args) == 0
    assert calls == [('discover', 'first')]
    assert state.read_bytes() == original
    assert 'update skipped' in capsys.readouterr().out
    controls['time'] = 110
    assert app.main(args) == 0
    assert calls[-1] == ('update', 'first')
    controls['ip'] = '192.0.2.2'
    assert app.main(args) == 0
    assert list(json.loads(state.read_text())['entries'].values())[0]['ipv4'] == '192.0.2.2'


def test_future_record_refreshes(setup):
    _, _, args, calls, controls, _ = setup
    assert app.main(args) == 0
    calls.clear()
    controls['time'] = 99
    assert app.main(args) == 0
    assert calls == [('discover', 'first'), ('update', 'first')]


@pytest.mark.parametrize('result', [None, False, 1, 'OK'])
def test_unverified_not_persisted(setup, result):
    _, state, args, calls, controls, _ = setup
    controls['result'] = result
    assert app.main(args) == 0
    assert not state.exists()
    assert app.main(args) == 0
    assert len([c for c in calls if c[0] == 'update']) == 2


@pytest.mark.parametrize('phase', ['init', 'first'])
def test_failure_never_recorded(setup, phase, capsys):
    _, state, args, _, controls, _ = setup
    controls['fail'] = phase
    assert app.main(args) == 1
    assert not state.exists()
    out = capsys.readouterr()
    assert SECRET not in out.out + out.err


def test_existing_record_not_replaced_on_failure(setup):
    _, state, args, _, controls, _ = setup
    assert app.main(args) == 0
    old = state.read_bytes()
    controls.update(ip='192.0.2.2', fail='first')
    assert app.main(args) == 1
    assert state.read_bytes() == old


@pytest.mark.parametrize('change', ['credential', 'section', 'setting'])
def test_identity_changes_force_update(setup, change):
    config, _, args, calls, _, _ = setup
    assert app.main(args) == 0
    text = config.read_text()
    text = text.replace(SECRET, 'new-secret') if change == 'credential' else text.replace('[first]', '[renamed]') if change == 'section' else text + 'hostname=other.example\n'
    config.write_text(text)
    calls.clear()
    assert app.main(args) == 0
    assert len(calls) == 2


def test_key_stable_order_and_provider_identity(setup):
    _, _, _, _, _, fake = setup
    key = app.service_state_key('first', fake, {'b': '2', 'a': '1'})
    assert key == app.service_state_key('first', fake, {'a': '1', 'b': '2'})
    class Other(fake):
        pass
    assert key != app.service_state_key('first', Other, {'b': '2', 'a': '1'})


@pytest.mark.parametrize('mode', ['corrupt', 'locked', 'missing-parent'])
def test_state_failure_prevents_discovery_and_logs(setup, mode, capsys):
    _, state, args, calls, _, _ = setup
    args.remove('--no-log')
    if mode == 'corrupt':
        state.write_text('SECRET')
    elif mode == 'locked':
        Path(str(state) + '.lock').write_text('owner')
    else:
        args[args.index('--state-file') + 1] = str(state.parent / 'missing' / 'state.json')
    assert app.main(args) == 1
    assert not calls
    assert not Path('ddns_update.log').exists()
    assert 'SECRET' not in capsys.readouterr().err


def test_dry_run_no_state_access(setup):
    _, state, args, calls, _, _ = setup
    state.write_text('not-json')
    Path(str(state) + '.lock').write_text('owner')
    assert app.main(args + ['--dry-run']) == 0
    assert not calls
    assert state.read_text() == 'not-json'
    assert sorted(p.name for p in state.parent.iterdir()) == ['config.ini', 'state.json', 'state.json.lock']


def test_save_failure_aborts_remaining_services(setup, monkeypatch, capsys):
    config, state, args, calls, _, _ = setup
    config.write_text(config.read_text() + f'[second]\nddns_provider=Fake\npassword={SECRET}\n')
    def fail(*args, **kwargs):
        raise update_state.StateError('write failed')
    monkeypatch.setattr(update_state.UpdateState, 'save', fail)
    assert app.main(args) == 1
    assert calls == [('discover', 'first'), ('update', 'first')]
    assert not state.exists() and not Path(str(state) + '.lock').exists()
    output = capsys.readouterr()
    assert 'accepted the update but state persistence failed' in output.err
    assert SECRET not in output.out + output.err


def test_later_service_runs_after_provider_failure(setup):
    config, state, args, calls, controls, _ = setup
    config.write_text(config.read_text() + f'[second]\nddns_provider=Fake\npassword={SECRET}\n')
    controls['fail'] = 'first'
    assert app.main(args) == 1
    assert calls[-1] == ('update', 'second')
    assert len(json.loads(state.read_text())['entries']) == 1


@pytest.mark.parametrize('extra', [ ['--state-file', '/absolute/state'], ['--refresh-seconds', '10'],
    ['--state-file', 'relative', '--refresh-seconds', '10'],
    ['--state-file', '/absolute/state', '--refresh-seconds', 'SECRET'],
    ['--state-file', '/absolute/state', '--refresh-seconds', '0'],
    ['--state-file', '/absolute/state', '--refresh-seconds', '-1'],
    ['--state-file', '/absolute/state', '--refresh-seconds', '١'],
    ['--state-file', '/absolute/state', '--refresh-seconds', '10000000000']])
def test_invalid_options_before_any_io(setup, extra, capsys):
    _, _, _, calls, _, _ = setup
    assert app.main(['--dry-run', *extra]) == 2
    assert not calls
    assert 'SECRET' not in capsys.readouterr().err


@pytest.mark.parametrize('target', ['config', 'log'])
def test_state_path_collision_rejected(setup, target):
    config, state, args, calls, _, _ = setup
    args[args.index('--state-file') + 1] = str(config if target == 'config' else state.parent / 'ddns_update.log')
    assert app.main(args) == 2
    assert not calls


def test_real_duckdns_adapter_request_counts(setup, monkeypatch):
    from types import SimpleNamespace
    from providers.provider_duckddns import DuckDNS
    config, state, args, _, controls, _ = setup
    config.write_text('[first]\nddns_provider=DuckDNS\nsubdomain=example\ntoken=secret-token\n')
    monkeypatch.setattr(app, 'load_provider_classes', lambda: {'DuckDNS': DuckDNS})
    urls = []
    def get(url, **kwargs):
        urls.append(url)
        return SimpleNamespace(status_code=200, text=IP if url == 'https://api.ipify.org' else 'OK', close=lambda: None)
    monkeypatch.setattr(requests, 'get', get)
    assert app.main(args) == 0
    assert state.exists()
    controls['time'] = 101
    assert app.main(args) == 0
    assert urls == ['https://api.ipify.org', 'https://www.duckdns.org/update', 'https://api.ipify.org']
