import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import requests
import ddns_updater as app
import update_state as state
from providers.provider_eurodyndns import EuroDynDNS

IP = '192.0.2.1'
SECRET = 'secret-token'


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    def blocked(*args, **kwargs):
        pytest.fail('Real HTTP prohibited')
    monkeypatch.setattr(requests.sessions.Session, 'request', blocked)
    calls = []
    control = {'body': 'SECRET', 'status': 401, 'now': 100}
    def get(url, **kwargs):
        calls.append(url)
        discovery = url == 'https://api.ipify.org'
        return SimpleNamespace(status_code=200 if discovery else control['status'],
                               text=IP if discovery else control['body'], close=lambda: None)
    monkeypatch.setattr(requests, 'get', get)
    monkeypatch.setattr(app.time, 'time', lambda: control['now'])
    monkeypatch.setattr(app, 'load_provider_classes', lambda: {'EuroDynDNS': EuroDynDNS})
    config = tmp_path / 'config.ini'
    config.write_text(f'[first]\nddns_provider=EuroDynDNS\nusername=user\npassword={SECRET}\nhostname=one.example.org\n')
    path = tmp_path / 'state.json'
    args = ['--no-log', '--state-file', str(path), '--refresh-seconds', '10']
    return config, path, args, calls, control


@pytest.mark.parametrize('status', [301, 400, 401, 403, 404, 429, 500, 503])
def test_http_stop_persisted_before_discovery(scenario, status, capsys):
    _, path, args, calls, control = scenario
    control['status'] = status
    assert app.main(args) == 1
    record = list(json.loads(path.read_text())['errors'].values())[0]
    assert record == {'kind': 'stop', 'recorded_at': 100, 'retry_at': None}
    calls.clear()
    control.update(now=999999, status=200, body='good')
    assert app.main(args) == 1 and calls == []
    out = capsys.readouterr()
    assert 'SECRET' not in out.out + out.err


@pytest.mark.parametrize('body', ['', 'GOOD', 'good SECRET', 'badauth', 'abuse', '!yours', 'notfqdn', 'nohost', 'numhost', 'dnserr', 'good 192.0.2.2', '<html>SECRET</html>'])
def test_unconfirmed_success_body_stops(scenario, body):
    _, path, args, calls, control = scenario
    control.update(status=200, body=body)
    assert app.main(args) == 1
    assert json.loads(path.read_text())['entries'] == {}
    calls.clear()
    assert app.main(args) == 1 and not calls


@pytest.mark.parametrize('body', ['good', 'nochg', 'good '+IP, 'nochg '+IP])
def test_acceptance_change_detection(scenario, body):
    config, path, args, calls, control = scenario
    control.update(status=200, body=body)
    assert app.main(args) == 0
    assert len(json.loads(path.read_text())['entries']) == 1
    calls.clear()
    control['now'] = 101
    assert app.main(args) == 0
    assert calls == ['https://api.ipify.org']


def test_state_required_before_network(scenario):
    _, path, _, calls, _ = scenario
    assert app.main(['--no-log']) == 2
    assert calls == [] and not path.exists()
    assert app.main(['--dry-run']) == 0
    assert calls == []


def test_configuration_changes_do_not_bypass_stop(scenario):
    config, _, args, calls, control = scenario
    assert app.main(args) == 1
    config.write_text(config.read_text().replace('[first]', '[renamed]').replace('username=user', 'username=other').replace(SECRET, 'new-secret').replace('one.example.org', 'two.example.org'))
    calls.clear()
    control.update(status=200, body='good')
    assert app.main(args) == 1 and not calls


def test_remaining_services_not_attempted_after_error(scenario):
    config, _, args, calls, _ = scenario
    config.write_text(config.read_text() + '[second]\nddns_provider=EuroDynDNS\nusername=other\npassword=other\nhostname=two.example.org\n')
    assert app.main(args) == 1 and len(calls) == 2
    calls.clear()
    assert app.main(args) == 1 and not calls


def test_explicit_clear_preserves_acceptance(scenario):
    _, path, args, _, control = scenario
    control.update(status=200, body='good')
    assert app.main(args) == 0
    accepted = json.loads(path.read_text())['entries']
    control.update(now=110, status=401)
    assert app.main(args) == 1
    with state.open_state(path) as store:
        store.clear_error(app.provider_error_key(EuroDynDNS, {}))
        store.save()
    assert json.loads(path.read_text())['entries'] == accepted
    control.update(now=111, status=200, body='good')
    assert app.main(args) == 0


def test_error_state_failure_aborts_and_releases_lock(scenario, monkeypatch, capsys):
    _, path, args, calls, _ = scenario
    def fail(*args, **kwargs):
        raise state.StateError('SECRET')
    monkeypatch.setattr(state.UpdateState, 'save', fail)
    assert app.main(args) == 1 and len(calls) == 2
    assert not Path(str(path) + '.lock').exists()
    assert 'SECRET' not in capsys.readouterr().err


def test_logging_sanitized(scenario):
    _, _, args, _, _ = scenario
    args.remove('--no-log')
    assert app.main(args) == 1
    assert app.main(args) == 1
    log = Path('ddns_update.log').read_text()
    assert 'requires intervention' in log and 'SECRET' not in log


def test_error_scope_independent():
    from providers.provider_noip import NoIP
    from providers.provider_dynu import Dynu
    from providers.provider_securepoint import SecurePoint
    key = app.provider_error_key(EuroDynDNS, {})
    assert key == app.provider_error_key(EuroDynDNS, {'username': 'different'})
    assert key not in {app.provider_error_key(cls, {}) for cls in (NoIP, Dynu, SecurePoint)}
