import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import requests
import ddns_updater as app
import update_state as state
from providers.provider_freedns import FreeDNS
from providers.provider_afraid import Afraid

IP = '192.0.2.1'
SECRET = 'secret-token'


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    def blocked(*args, **kwargs):
        pytest.fail('Real HTTP prohibited')
    monkeypatch.setattr(requests.sessions.Session, 'request', blocked)
    calls = []
    control = {'body': 'abuse', 'status': 200, 'now': 100}
    def get(url, **kwargs):
        calls.append(url)
        discovery = url == 'https://api.ipify.org'
        return SimpleNamespace(status_code=200 if discovery else control['status'],
                               text=IP if discovery else control['body'], close=lambda: None)
    monkeypatch.setattr(requests, 'get', get)
    monkeypatch.setattr(app.time, 'time', lambda: control['now'])
    monkeypatch.setattr(app, 'load_provider_classes', lambda: {'FreeDNS': FreeDNS, 'Afraid': Afraid})
    config = tmp_path / 'config.ini'
    config.write_text(f'[first]\nddns_provider=FreeDNS\napi_key={SECRET}\nhostname=one.example\n')
    path = tmp_path / 'state.json'
    args = ['--no-log', '--state-file', str(path), '--refresh-seconds', '10']
    return config, path, args, calls, control


@pytest.mark.parametrize('code', ['Rejected SECRET', '', 'ERROR: Address 192.0.2.2 has not changed.', 'Updated one.example to 192.0.2.2 in 1 seconds', 'Updated wrong.example to '+IP+' in 1 seconds', '<html>SECRET</html>'])
def test_stops_persist_across_alias_and_account_changes(scenario, code, capsys):
    config, path, args, calls, control = scenario
    control['body'] = code
    assert app.main(args) == 1
    record = list(json.loads(path.read_text())['errors'].values())[0]
    assert record == {'kind': 'stop', 'recorded_at': 100, 'retry_at': None}
    calls.clear()
    config.write_text(config.read_text().replace('FreeDNS', 'Afraid').replace('[first]', '[renamed]').replace('one.example', 'two.example').replace(SECRET, 'new-token'))
    control.update(now=999999, body='Updated one.example to '+IP+' in 1 seconds.')
    assert app.main(args) == 1
    assert calls == []
    out = capsys.readouterr()
    assert SECRET not in out.out + out.err and 'SECRET' not in out.out + out.err


@pytest.mark.parametrize('cls', [FreeDNS, Afraid])
@pytest.mark.parametrize('body', ['Updated one.example to '+IP+' in 1 seconds.', 'Updated 1 host(s) one.example to '+IP+' in 0.2 seconds', 'ERROR: Address '+IP+' has not changed.'])
def test_acceptance_and_change_detection(scenario, cls, body):
    config, path, args, calls, control = scenario
    config.write_text(config.read_text().replace('FreeDNS', cls.__name__))
    control['body'] = body
    assert app.main(args) == 0
    data = json.loads(path.read_text())
    assert data['errors'] == {} and len(data['entries']) == 1
    calls.clear()
    control['now'] = 101
    assert app.main(args) == 0
    assert calls == ['https://api.ipify.org']


@pytest.mark.parametrize('status', [301, 401, 403, 429, 500, 503])
def test_http_stops(scenario, status):
    _, path, args, calls, control = scenario
    control.update(status=status, body='SECRET')
    assert app.main(args) == 1
    assert list(json.loads(path.read_text())['errors'].values())[0]['kind'] == 'stop'
    calls.clear()
    assert app.main(args) == 1 and not calls


@pytest.mark.parametrize('cls', [FreeDNS, Afraid])
def test_state_required_before_discovery(scenario, cls):
    config, _, _, calls, _ = scenario
    config.write_text(config.read_text().replace('FreeDNS', cls.__name__))
    assert app.main(['--no-log']) == 2
    assert calls == []
    assert app.main(['--dry-run']) == 0
    assert calls == []


def test_shared_error_identity_independent_of_other_providers():
    from providers.provider_noip import NoIP
    from providers.provider_dynu import Dynu
    key = app.provider_error_key(FreeDNS, {})
    assert key == app.provider_error_key(Afraid, {'username': 'different'})
    assert key != app.provider_error_key(NoIP, {})
    assert key != app.provider_error_key(Dynu, {})


def test_explicit_clear_preserves_acceptance(scenario):
    _, path, args, _, control = scenario
    control['body'] = 'Updated one.example to '+IP+' in 1 seconds.'
    assert app.main(args) == 0
    entries = json.loads(path.read_text())['entries']
    control.update(now=110, body='abuse')
    assert app.main(args) == 1
    with state.open_state(path) as store:
        store.clear_error(app.provider_error_key(Afraid, {}))
        store.save()
    assert json.loads(path.read_text())['entries'] == entries
    control.update(now=111, body='Updated one.example to '+IP+' in 1 seconds.')
    assert app.main(args) == 0


def test_mixed_alias_tasks_are_not_attempted_after_stop(scenario):
    config, _, args, calls, _ = scenario
    config.write_text(config.read_text() + '[second]\nddns_provider=Afraid\napi_key=other\nhostname=two.example\n')
    assert app.main(args) == 1
    assert len(calls) == 2
    calls.clear()
    assert app.main(args) == 1 and not calls


def test_persistence_failure_stops_releases_lock(scenario, monkeypatch, capsys):
    _, path, args, calls, _ = scenario
    def fail(*args, **kwargs):
        raise state.StateError('SECRET')
    monkeypatch.setattr(state.UpdateState, 'save', fail)
    assert app.main(args) == 1
    assert len(calls) == 2
    assert not Path(str(path)+'.lock').exists()
    assert 'SECRET' not in capsys.readouterr().err


def test_error_logs_are_sanitized(scenario):
    _, _, args, _, control = scenario
    args.remove('--no-log')
    control['body'] = 'malformed '+SECRET
    assert app.main(args) == 1
    assert app.main(args) == 1
    text = Path('ddns_update.log').read_text()
    assert 'requires intervention' in text and SECRET not in text
