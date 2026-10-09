import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import requests
import ddns_updater as app
import update_state as state
from providers.provider_noip import NoIP
from providers.ddns_provider import ProviderRetryError, ProviderStopError

IP = '192.0.2.1'
SECRET = 'secret-token'


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    def blocked(*args, **kwargs):
        pytest.fail('Real HTTP prohibited')
    monkeypatch.setattr(requests.sessions.Session, 'request', blocked)
    calls = []
    control = {'body': '911', 'status': 200, 'now': 100}
    def get(url, **kwargs):
        calls.append(url)
        discovery = url == 'https://api.ipify.org'
        return SimpleNamespace(status_code=200 if discovery else control['status'],
                               text=IP if discovery else control['body'], close=lambda: None)
    monkeypatch.setattr(requests, 'get', get)
    monkeypatch.setattr(app.time, 'time', lambda: control['now'])
    monkeypatch.setattr(app, 'load_provider_classes', lambda: {'NoIP': NoIP})
    config = tmp_path / 'config.ini'
    config.write_text(f'[first]\nddns_provider=NoIP\nusername=user\npassword={SECRET}\nhostname=one.example\n')
    path = tmp_path / 'state.json'
    args = ['--no-log', '--state-file', str(path), '--refresh-seconds', '10']
    return config, path, args, calls, control


@pytest.mark.parametrize('body,status', [('911', 200), ('SECRET', 500)])
def test_cooldown_persisted_before_discovery_and_expires(scenario, body, status):
    _, path, args, calls, control = scenario
    control.update(body=body, status=status)
    assert app.main(args) == 1
    data = json.loads(path.read_text())
    assert data['entries'] == {}
    record = list(data['errors'].values())[0]
    assert record == {'kind': 'cooldown', 'recorded_at': 100, 'retry_at': 1900}
    calls.clear()
    control['now'] = 1899
    assert app.main(args) == 1
    assert calls == []
    control.update(now=1900, body='good ' + IP, status=200)
    assert app.main(args) == 0
    assert len(calls) == 2
    assert json.loads(path.read_text())['errors'] == {}


@pytest.mark.parametrize('body', ['badauth', 'badagent', 'abuse', 'nohost', '!donator', 'malformed SECRET'])
def test_stop_persists_and_cannot_be_bypassed_by_config_changes(scenario, body, capsys):
    config, path, args, calls, control = scenario
    control['body'] = body
    assert app.main(args) == 1
    calls.clear()
    control.update(now=999999, body='good ' + IP)
    config.write_text(config.read_text().replace('[first]', '[renamed]').replace('username=user', 'username=other').replace(SECRET, 'new-token') + 'user_agent=NewClient/1.0\n')
    assert app.main(args) == 1
    assert calls == []
    assert list(json.loads(path.read_text())['errors'].values())[0]['kind'] == 'stop'
    output = capsys.readouterr()
    assert SECRET not in output.out + output.err and 'SECRET' not in output.out + output.err


def test_noip_state_required_before_network(scenario):
    _, path, _, calls, _ = scenario
    assert app.main(['--no-log']) == 2
    assert not calls and not path.exists()
    assert app.main(['--dry-run']) == 0
    assert not calls


def test_error_stops_remaining_services_and_blocks_other_account_next_run(scenario):
    config, _, args, calls, control = scenario
    config.write_text(config.read_text() + '[second]\nddns_provider=NoIP\nusername=other\npassword=other\nhostname=two.example\n')
    assert app.main(args) == 1
    assert len(calls) == 2
    calls.clear()
    assert app.main(args) == 1
    assert calls == []


@pytest.mark.parametrize('body,exception', [('good '+IP+'\n911', ProviderRetryError),
    ('good '+IP+'\nbadauth', ProviderStopError), ('911\nabuse', ProviderStopError)])
def test_partial_and_global_responses(scenario, body, exception):
    _, _, _, _, control = scenario
    control['body'] = body
    provider = NoIP('test', {'username': 'user', 'password': SECRET, 'hostname': 'one,two'})
    with pytest.raises(exception):
        provider.update_ddns()


def test_error_save_failure_stops_and_releases_lock(scenario, monkeypatch, capsys):
    _, path, args, calls, _ = scenario
    def fail(*args, **kwargs):
        raise state.StateError('SECRET')
    monkeypatch.setattr(state.UpdateState, 'save', fail)
    assert app.main(args) == 1
    assert len(calls) == 2
    assert not Path(str(path) + '.lock').exists()
    output = capsys.readouterr()
    assert 'Cannot persist provider error controls' in output.err
    assert 'SECRET' not in output.out + output.err


def test_v1_read_and_upgrade_preserves_acceptance(tmp_path):
    key = 'a' * 64
    path = tmp_path / 'state.json'
    record = {'ipv4': IP, 'accepted_at': 100}
    path.write_text(json.dumps({'version': 1, 'entries': {key: record}}))
    with state.open_state(path) as store:
        assert store.matches(key, IP, now=101, max_age=10)
        store.record_error('b' * 64, now=101, retry_seconds=1800)
        store.save()
    data = json.loads(path.read_text())
    assert data['version'] == 2 and data['entries'] == {key: record}


@pytest.mark.parametrize('record', [{'kind': 'unknown', 'recorded_at': 100, 'retry_at': None},
    {'kind': 'stop', 'recorded_at': True, 'retry_at': None},
    {'kind': 'stop', 'recorded_at': 100, 'retry_at': 200},
    {'kind': 'cooldown', 'recorded_at': 100, 'retry_at': None},
    {'kind': 'cooldown', 'recorded_at': 100, 'retry_at': 100},
    {'kind': 'cooldown', 'recorded_at': 100, 'retry_at': 99}, {}])
def test_invalid_error_state_fails_closed(tmp_path, record):
    path = tmp_path / 'state.json'
    path.write_text(json.dumps({'version': 2, 'entries': {}, 'errors': {'a' * 64: record}}))
    with pytest.raises(state.StateError):
        with state.open_state(path):
            pass


def test_clock_rollback_and_explicit_clear(tmp_path):
    path = tmp_path / 'state.json'
    with state.open_state(path) as store:
        store.record_error('a' * 64, now=100, retry_seconds=1800)
        assert store.blocked('a' * 64, now=99) == 'cooldown'
        store.record_error('b' * 64, now=100)
        assert store.blocked('b' * 64, now=999999) == 'stop'
        store.clear_error('b' * 64)
        assert store.blocked('b' * 64, now=100) is None


def test_controls_logged_without_provider_body(scenario):
    _, _, args, _, control = scenario
    args.remove('--no-log')
    control['body'] = 'malformed ' + SECRET
    assert app.main(args) == 1
    assert app.main(args) == 1
    log = Path('ddns_update.log').read_text()
    assert 'requires intervention' in log
    assert SECRET not in log


@pytest.mark.parametrize('seconds', [0, -1, True, 1.5])
def test_invalid_retry_interval(tmp_path, seconds):
    with state.open_state(tmp_path / 'state.json') as store:
        with pytest.raises(state.StateError):
            store.record_error('a' * 64, now=100, retry_seconds=seconds)
        assert store.errors == {}


def test_error_entry_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(state.UpdateState, 'max_entries', 1)
    with state.open_state(tmp_path / 'state.json') as store:
        store.record_error('a' * 64, now=100)
        with pytest.raises(state.StateError):
            store.record_error('b' * 64, now=100)
        store.record_error('a' * 64, now=101, retry_seconds=1800)
