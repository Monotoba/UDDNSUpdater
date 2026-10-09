import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import requests
import ddns_updater as app
import update_state as state
from providers.provider_dynu import Dynu

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
    monkeypatch.setattr(app, 'load_provider_classes', lambda: {'Dynu': Dynu})
    config = tmp_path / 'config.ini'
    config.write_text(f'[first]\nddns_provider=Dynu\nusername=user\npassword={SECRET}\nhostname=one.example\n')
    path = tmp_path / 'state.json'
    args = ['--no-log', '--state-file', str(path), '--refresh-seconds', '10']
    return config, path, args, calls, control


@pytest.mark.parametrize('code', ['911', 'servererror', 'dnserr', '911 SECRET', 'servererror SECRET', 'dnserr SECRET'])
def test_retry_codes_persist_block_before_discovery_and_expire(scenario, code, capsys):
    _, path, args, calls, control = scenario
    control['body'] = code
    assert app.main(args) == 1
    data = json.loads(path.read_text())
    assert data['entries'] == {}
    assert list(data['errors'].values()) == [{'kind': 'cooldown', 'recorded_at': 100, 'retry_at': 700}]
    calls.clear()
    control['now'] = 699
    assert app.main(args) == 1
    assert calls == []
    control.update(now=700, body='good ' + IP)
    assert app.main(args) == 0
    assert len(calls) == 2
    assert json.loads(path.read_text())['errors'] == {}
    out = capsys.readouterr()
    assert 'SECRET' not in out.out + out.err


@pytest.mark.parametrize('code', ['unknown', 'badauth', 'notfqdn', 'numhost', 'abuse', 'nohost', '!donator',
                                 'malformed SECRET', 'good 192.0.2.2', 'good '+IP+' extra'])
def test_stop_response_persists_across_identity_changes(scenario, code):
    config, path, args, calls, control = scenario
    control['body'] = code
    assert app.main(args) == 1
    calls.clear()
    config.write_text(config.read_text().replace('[first]', '[renamed]').replace('username=user', 'username=other').replace(SECRET, 'new-token'))
    control.update(now=999999, body='good ' + IP)
    assert app.main(args) == 1
    assert calls == []
    assert list(json.loads(path.read_text())['errors'].values())[0]['kind'] == 'stop'


@pytest.mark.parametrize('status', [301, 401, 403, 429, 500, 502, 503, 504])
def test_http_rejections_are_conservative_stops(scenario, status):
    _, path, args, calls, control = scenario
    control.update(status=status, body='SECRET')
    assert app.main(args) == 1
    assert list(json.loads(path.read_text())['errors'].values())[0]['kind'] == 'stop'
    calls.clear()
    assert app.main(args) == 1 and not calls


def test_requires_state_before_network_but_dry_run_allowed(scenario):
    _, path, _, calls, _ = scenario
    assert app.main(['--no-log']) == 2
    assert not calls and not path.exists()
    assert app.main(['--dry-run']) == 0
    assert not calls


def test_error_stops_remaining_accounts(scenario):
    config, _, args, calls, _ = scenario
    config.write_text(config.read_text() + '[second]\nddns_provider=Dynu\nusername=other\npassword=other\nhostname=two.example\n')
    assert app.main(args) == 1
    assert len(calls) == 2
    calls.clear()
    assert app.main(args) == 1 and not calls


def test_save_error_aborts_and_releases_lock(scenario, monkeypatch, capsys):
    _, path, args, calls, _ = scenario
    def fail(*args, **kwargs):
        raise state.StateError('SECRET')
    monkeypatch.setattr(state.UpdateState, 'save', fail)
    assert app.main(args) == 1
    assert len(calls) == 2
    assert not Path(str(path) + '.lock').exists()
    assert 'SECRET' not in capsys.readouterr().err


def test_dynu_scope_does_not_block_noip(scenario):
    from providers.provider_noip import NoIP
    _, path, args, _, _ = scenario
    assert app.main(args) == 1
    with state.open_state(path) as store:
        assert store.blocked(app.provider_error_key(Dynu, {}), now=101) == 'cooldown'
        assert store.blocked(app.provider_error_key(NoIP, {}), now=101) is None


def test_control_logs_are_sanitized(scenario):
    _, _, args, _, control = scenario
    args.remove('--no-log')
    control['body'] = 'badauth ' + SECRET
    assert app.main(args) == 1
    assert app.main(args) == 1
    log = Path('ddns_update.log').read_text()
    assert 'requires intervention' in log and SECRET not in log
