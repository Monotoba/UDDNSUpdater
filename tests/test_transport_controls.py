import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import requests
import ddns_updater as app
import update_state as state
from providers.provider_duckddns import DuckDNS
from providers.provider_godaddy import GoDaddyDDNS
from providers.ddns_provider import DDNSProvider, ProviderRetryError

IP = '192.0.2.1'
SECRET = 'private-token'

@pytest.fixture
def scenario(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(requests.sessions.Session, 'request', lambda *a, **k: pytest.fail('Real HTTP prohibited'))
    config = tmp_path/'config.ini'
    config.write_text('[first]\nddns_provider=DuckDNS\nsubdomain=one\ntoken='+SECRET+'\n')
    path = tmp_path/'state.json'
    calls = []
    control = {'now': 100, 'failure': 'discovery', 'error': requests.Timeout(SECRET), 'status': 200}
    def request(url, **kwargs):
        calls.append(url)
        discovery = url == 'https://api.ipify.org'
        if control['failure'] == ('discovery' if discovery else 'update'):
            raise control['error']
        return SimpleNamespace(status_code=control['status'] if discovery else 200,
                               text=IP if discovery else ('OK' if 'duckdns' in url else ''), close=lambda: None)
    monkeypatch.setattr(requests, 'get', request)
    monkeypatch.setattr(requests, 'put', request)
    monkeypatch.setattr(app.time, 'time', lambda: control['now'])
    args = ['--no-log', '--state-file', str(path), '--refresh-seconds', '60']
    return config, path, calls, control, args

@pytest.mark.parametrize('stage', ['discovery', 'update'])
@pytest.mark.parametrize('error', [requests.Timeout(SECRET), requests.ConnectionError(SECRET), requests.exceptions.SSLError(SECRET)])
@pytest.mark.parametrize('cls', [DuckDNS, GoDaddyDDNS])
def test_transport_cooldown_persists_until_boundary(scenario, cls, stage, error, capsys):
    config, path, calls, control, args = scenario
    if cls is GoDaddyDDNS:
        config.write_text('[first]\nddns_provider=GoDaddyDDNS\napi_key=key\napi_secret='+SECRET+'\ndomain=example.org\nhostname=@\n')
    control.update(failure=stage, error=error)
    assert app.main(args) == 1
    data = json.loads(path.read_text())
    assert data['entries'] == {}
    assert list(data['errors'].values()) == [{'kind': 'cooldown', 'recorded_at': 100, 'retry_at': 1900}]
    calls.clear()
    control.update(now=1899, failure=None)
    assert app.main(args) == 1 and calls == []
    control['now'] = 1900
    assert app.main(args) == 0 and len(calls) == 2
    assert json.loads(path.read_text())['errors'] == {}
    output = capsys.readouterr()
    assert SECRET not in output.out+output.err

@pytest.mark.parametrize('status', [301, 400, 401, 429, 500, 503])
def test_discovery_http_rejection_is_cooldown(scenario, status):
    _, path, calls, control, args = scenario
    control.update(failure=None, status=status)
    assert app.main(args) == 1 and len(calls) == 1
    assert list(json.loads(path.read_text())['errors'].values())[0]['retry_at'] == 1900
    calls.clear()
    assert app.main(args) == 1 and calls == []

def test_transport_error_aborts_remaining_services(scenario):
    config, _, calls, _, args = scenario
    config.write_text(config.read_text()+'[second]\nddns_provider=CloudNS\napi_key=other\nhostname=other\n')
    assert app.main(args) == 1 and len(calls) == 1

def test_save_failure_aborts_and_releases_lock(scenario, monkeypatch, capsys):
    _, path, calls, _, args = scenario
    def fail(*a, **k):
        raise state.StateError(SECRET)
    monkeypatch.setattr(state.UpdateState, 'save', fail)
    assert app.main(args) == 1 and len(calls) == 1
    assert not Path(str(path)+'.lock').exists()
    assert SECRET not in capsys.readouterr().err

def test_direct_transport_failure_is_typed_without_state(monkeypatch):
    def fail(*a, **k):
        raise requests.Timeout(SECRET)
    monkeypatch.setattr(requests, 'get', fail)
    with pytest.raises(ProviderRetryError) as error:
        DDNSProvider('test', {})
    assert error.value.retry_seconds == 1800
    assert SECRET not in str(error.value)
