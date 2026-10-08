import pytest
import requests

import ddns_updater
from providers.ddns_provider import ProviderError
from providers.provider_afraid import Afraid
from providers.provider_freedns import FreeDNS

IP = '203.0.113.42'
KEY = 'secret+/=='
HOST = 'example.mooo.com'
CONFIG = {'api_key': KEY, 'hostname': HOST}


@pytest.fixture(autouse=True)
def no_live_http(monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail('Real HTTP prohibited')
    monkeypatch.setattr(requests.sessions.Session, 'request', fail)


class Response:
    def __init__(self, text, status=200):
        self.text, self.status_code, self.closed = text, status, False
    def close(self):
        self.closed = True


def mock_http(monkeypatch, body, status=200):
    replies = [Response(IP), Response(body, status)]
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        return replies[len(calls)-1]
    monkeypatch.setattr(requests, 'get', get)
    return calls, replies


@pytest.mark.parametrize('cls', [FreeDNS, Afraid])
@pytest.mark.parametrize('body', [f'Updated {HOST} to {IP} in 0.123 seconds',
    f'Updated 1 host(s) {HOST} to {IP} in 1 seconds.\n',
    f'ERROR: Address {IP} has not changed.'])
def test_acceptance_and_encoded_request(monkeypatch, cls, body):
    calls, replies = mock_http(monkeypatch, body)
    assert cls('service', CONFIG).update_ddns() is True
    url, options = calls[1]
    assert url == 'https://freedns.afraid.org/dynamic/update.php?secret%2B%2F%3D%3D'
    assert options['params'] == {'address': IP}
    assert options['timeout'] == (5, 15)
    assert options['allow_redirects'] is False
    assert 'auth' not in options and 'headers' not in options
    assert all(response.closed for response in replies)
    prepared = requests.Request('GET', url, params=options['params']).prepare()
    assert prepared.url.endswith('?secret%2B%2F%3D%3D&address='+IP)


@pytest.mark.parametrize('cls', [FreeDNS, Afraid])
@pytest.mark.parametrize('body', ['', 'Updated', 'Not Updated', '<html>Updated</html>',
    f'Updated wrong.mooo.com to {IP} in 0.1 seconds',
    f'Updated {HOST} to 203.0.113.43 in 0.1 seconds',
    'ERROR: Address 203.0.113.43 has not changed.',
    f'Updated {HOST} to {IP} in 0.1 seconds\nERROR: rejected',
    f'ERROR: {KEY}'])
def test_rejected_bodies(monkeypatch, cls, body):
    _, replies = mock_http(monkeypatch, body)
    with pytest.raises(ProviderError) as error:
        cls('service', CONFIG).update_ddns()
    assert KEY not in str(error.value)
    assert all(response.closed for response in replies)


@pytest.mark.parametrize('status', [301, 400, 401, 403, 500])
def test_http_failures(monkeypatch, status):
    _, replies = mock_http(monkeypatch, KEY, status)
    with pytest.raises(ProviderError) as error:
        FreeDNS('service', CONFIG).update_ddns()
    assert KEY not in str(error.value)
    assert all(response.closed for response in replies)


@pytest.mark.parametrize('key', ['', 'https://freedns.afraid.org/dynamic/update.php?key',
    'key&offline=1', 'key#fragment', 'key\n', 'key with spaces', 'key?other'])
def test_invalid_keys_before_discovery(monkeypatch, key):
    calls, _ = mock_http(monkeypatch, 'unused')
    with pytest.raises(ProviderError):
        FreeDNS('service', dict(CONFIG, api_key=key))
    assert not calls


@pytest.mark.parametrize('cls', [FreeDNS, Afraid])
def test_cli_rejection_returns_failure_without_secrets(monkeypatch, tmp_path, capsys, cls):
    monkeypatch.chdir(tmp_path)
    (tmp_path/'config.ini').write_text('[service]\nddns_provider='+cls.__name__+'\n'+
        '\n'.join(f'{k}={v}' for k,v in CONFIG.items()))
    mock_http(monkeypatch, 'Rejected '+KEY)
    assert ddns_updater.main(['--no-log']) == 1
    output = capsys.readouterr()
    assert KEY not in output.out+output.err


def test_old_afraid_credentials_fail_before_any_requests(monkeypatch, tmp_path):
    path=tmp_path/'config.ini'
    path.write_text('[service]\nddns_provider=Afraid\nusername=user\npassword=secret\nhostname='+HOST)
    calls, _ = mock_http(monkeypatch, 'unused')
    assert ddns_updater.main(['--config-file', str(path), '--dry-run']) == 2
    assert not calls


def test_transport_failure_is_sanitized(monkeypatch):
    provider = FreeDNS.__new__(FreeDNS)
    provider.config, provider.api_key, provider.external_ip = CONFIG, KEY, IP
    def fail(*args, **kwargs):
        raise requests.RequestException('request URL exposed '+KEY)
    monkeypatch.setattr(requests, 'get', fail)
    with pytest.raises(ProviderError) as error:
        provider.update_ddns()
    assert KEY not in str(error.value)
