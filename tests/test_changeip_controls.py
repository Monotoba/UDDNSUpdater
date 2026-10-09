import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import requests
import ddns_updater as app
import update_state as state
from providers.provider_changeip import ChangeIP
from providers.ddns_provider import ProviderError

IP = '192.0.2.1'
SECRET = 'secret-token'


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    def blocked(*args, **kwargs):
        pytest.fail('Real HTTP prohibited')
    monkeypatch.setattr(requests.sessions.Session, 'request', blocked)
    calls = []
    control = {'body': '422 SECRET', 'status': 200, 'now': 100}
    def get(url, **kwargs):
        calls.append(url)
        discovery = url == 'https://api.ipify.org'
        return SimpleNamespace(status_code=200 if discovery else control['status'],
                               text=IP if discovery else control['body'], close=lambda: None)
    monkeypatch.setattr(requests, 'get', get)
    monkeypatch.setattr(app.time, 'time', lambda: control['now'])
    monkeypatch.setattr(app, 'load_provider_classes', lambda: {'ChangeIP': ChangeIP})
    config = tmp_path / 'config.ini'
    config.write_text(f'[first]\nddns_provider=ChangeIP\nusername=user\npassword={SECRET}\nhostname=one.example\n')
    path = tmp_path / 'state.json'
    args = ['--no-log', '--state-file', str(path), '--refresh-seconds', '10']
    return config, path, args, calls, control


@pytest.mark.parametrize('body', ['402 Premium DNS required', '422 Invalid hostname', '911', 'badauth',
    '', 'SECRET', '<html>200 Successful Update</html>', '200 Successful Update (Address Used: 192.0.2.2)'])
def test_rejected_bodies_persist_and_block_before_discovery(scenario, body, capsys):
    config, path, args, calls, control = scenario
    control['body'] = body
    assert app.main(args) == 1
    assert json.loads(path.read_text())['entries'] == {}
    assert list(json.loads(path.read_text())['errors'].values()) == [{'kind': 'stop', 'recorded_at': 100, 'retry_at': None}]
    calls.clear()
    config.write_text(config.read_text().replace('[first]', '[renamed]').replace('username=user', 'username=other').replace(SECRET, 'new-secret'))
    control.update(now=999999, body='200 Successful Update')
    assert app.main(args) == 1 and not calls
    output = capsys.readouterr()
    assert 'SECRET' not in output.out + output.err


@pytest.mark.parametrize('status', [301, 400, 401, 402, 422, 429, 500, 503])
def test_http_stops(scenario, status):
    _, path, args, calls, control = scenario
    control.update(status=status, body='SECRET')
    assert app.main(args) == 1
    assert list(json.loads(path.read_text())['errors'].values())[0]['kind'] == 'stop'
    calls.clear()
    assert app.main(args) == 1 and not calls


@pytest.mark.parametrize('body', ['200 Successful Update', '200 Successful Update (Address Used: '+IP+')',
    '200 Successful Update\nDiagnostic details'])
def test_success_and_change_detection_retained(scenario, body):
    _, path, args, calls, control = scenario
    control['body'] = body
    assert app.main(args) == 0
    assert len(json.loads(path.read_text())['entries']) == 1
    calls.clear()
    control['now'] = 101
    assert app.main(args) == 0
    assert calls == ['https://api.ipify.org']


@pytest.mark.parametrize('host', ['host.changeip.com', 'HOST.CHANGEIP.COM.', 'changeip.com',
    'nested.host.changeip.com', 'one.example, host.changeip.com'])
def test_discontinued_targets_fail_before_discovery_and_state(scenario, host):
    config, path, args, calls, _ = scenario
    config.write_text(config.read_text().replace('one.example', host))
    assert app.main(args) == 2
    assert app.main(['--dry-run']) == 2
    assert not calls and not path.exists() and not Path(str(path) + '.lock').exists()
    with pytest.raises(ProviderError):
        ChangeIP('direct', {'hostname': host, 'username': 'user', 'password': SECRET})
    assert not calls


@pytest.mark.parametrize('host', ['example.com', 'host.changeip.com.example.org', 'mychangeip.com', '*1', '*2'])
def test_other_targets_and_sets_not_mistaken_for_retired_suffix(scenario, host):
    config, _, _, calls, _ = scenario
    config.write_text(config.read_text().replace('one.example', host))
    assert app.main(['--dry-run']) == 0
    assert not calls


def test_invalid_later_target_prevents_all_requests(scenario):
    config, path, args, calls, _ = scenario
    config.write_text(config.read_text() + '[second]\nddns_provider=ChangeIP\nusername=other\npassword=other\nhostname=retired.changeip.com\n')
    assert app.main(args) == 2
    assert not calls and not path.exists()


def test_state_required(scenario):
    _, _, _, calls, _ = scenario
    assert app.main(['--no-log']) == 2
    assert not calls


def test_explicit_clear_preserves_acceptance(scenario):
    _, path, args, _, control = scenario
    control['body'] = '200 Successful Update'
    assert app.main(args) == 0
    accepted = json.loads(path.read_text())['entries']
    control.update(now=110, body='422 invalid')
    assert app.main(args) == 1
    with state.open_state(path) as store:
        store.clear_error(app.provider_error_key(ChangeIP, {}))
        store.save()
    assert json.loads(path.read_text())['entries'] == accepted
    control.update(now=111, body='200 Successful Update')
    assert app.main(args) == 0


def test_error_save_failure_stops_and_unlocks(scenario, monkeypatch, capsys):
    _, path, args, calls, _ = scenario
    def fail(*args, **kwargs):
        raise state.StateError('SECRET')
    monkeypatch.setattr(state.UpdateState, 'save', fail)
    assert app.main(args) == 1 and len(calls) == 2
    assert not Path(str(path) + '.lock').exists()
    assert 'SECRET' not in capsys.readouterr().err


def test_logs_sanitized(scenario):
    _, _, args, _, _ = scenario
    args.remove('--no-log')
    assert app.main(args) == 1
    assert app.main(args) == 1
    log = Path('ddns_update.log').read_text()
    assert 'requires intervention' in log and 'SECRET' not in log
