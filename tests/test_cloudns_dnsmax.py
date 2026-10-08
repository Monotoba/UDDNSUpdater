import pytest
import requests

import ddns_updater
from providers.ddns_provider import ProviderError
from providers.provider_cloudns import CloudNS
from providers.provider_dnsmax import DNSMax

IP = '203.0.113.42'
SECRET = 'key%with&ip=wrong+/?'
CONFIG = {'api_key': SECRET, 'hostname': 'home.example.net'}


@pytest.fixture(autouse=True)
def prohibit_http(monkeypatch):
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


@pytest.mark.parametrize('body', ['OK', ' OK\n'])
def test_cloudns_encoded_request_and_acceptance(monkeypatch, body):
    from urllib.parse import parse_qs, urlsplit
    calls, replies = mock_http(monkeypatch, body)
    adapter = CloudNS('service', CONFIG)
    assert adapter.hostname == CONFIG['hostname']
    assert adapter.update_ddns() is True
    url, options = calls[1]
    assert url == 'https://ipv4.cloudns.net/api/dynamicURL/'
    assert options['params'] == {'q': SECRET, 'ip': IP}
    assert options['timeout'] == (5, 15)
    assert options['allow_redirects'] is False
    assert 'auth' not in options and 'headers' not in options
    prepared = requests.Request('GET', url, params=options['params']).prepare()
    assert parse_qs(urlsplit(prepared.url).query) == {'q': [SECRET], 'ip': [IP]}
    assert all(reply.closed for reply in replies)


@pytest.mark.parametrize('body', ['', 'success', 'not OK', 'OK error', 'ok', '<html>OK</html>',
    '{"status":"OK"}', 'OK\nERROR: '+SECRET, SECRET])
def test_cloudns_bad_response_fails(monkeypatch, body):
    _, replies = mock_http(monkeypatch, body)
    with pytest.raises(ProviderError) as error:
        CloudNS('service', CONFIG).update_ddns()
    assert SECRET not in str(error.value)
    assert all(reply.closed for reply in replies)


@pytest.mark.parametrize('status', [204, 301, 302, 400, 401, 403, 404, 500])
def test_cloudns_http_failure(monkeypatch, status):
    _, replies = mock_http(monkeypatch, SECRET, status)
    with pytest.raises(ProviderError) as error:
        CloudNS('service', CONFIG).update_ddns()
    assert SECRET not in str(error.value)
    assert all(reply.closed for reply in replies)


def test_cloudns_timeout_is_sanitized_and_not_retried(monkeypatch):
    adapter = CloudNS.__new__(CloudNS)
    adapter.config, adapter.api_key, adapter.external_ip = CONFIG, SECRET, IP
    calls = []
    def fail(*args, **kwargs):
        calls.append((args, kwargs))
        raise requests.Timeout('URL with '+SECRET)
    monkeypatch.setattr(requests, 'get', fail)
    with pytest.raises(ProviderError) as error:
        adapter.update_ddns()
    assert SECRET not in str(error.value)
    assert len(calls) == 1


@pytest.mark.parametrize('ip', ['bad', '2001:db8::1'])
def test_cloudns_invalid_ipv4_prevents_update(monkeypatch, ip):
    adapter = CloudNS.__new__(CloudNS)
    adapter.config, adapter.api_key, adapter.external_ip = CONFIG, SECRET, ip
    calls, _ = mock_http(monkeypatch, 'unused')
    with pytest.raises(ProviderError):
        adapter.update_ddns()
    assert not calls


@pytest.mark.parametrize('body,expected', [('OK', 0), ('rejected '+SECRET, 1)])
def test_cloudns_cli_status_and_redaction(monkeypatch, tmp_path, capsys, body, expected):
    path = tmp_path/'config.ini'
    path.write_text('[service]\nddns_provider=CloudNS\n'+
        '\n'.join(f'{k}={v}' for k,v in CONFIG.items()))
    mock_http(monkeypatch, body)
    assert ddns_updater.main(['--config-file', str(path), '--no-log']) == expected
    output = capsys.readouterr()
    assert SECRET not in output.out+output.err
    if expected == 0:
        assert 'provider accepted' in output.out


def test_old_cloudns_config_fails_before_requests(monkeypatch, tmp_path):
    path = tmp_path/'config.ini'
    path.write_text('[service]\nddns_provider=CloudNS\nusername=user\npassword=secret\nhostname=home.example.net')
    calls, _ = mock_http(monkeypatch, 'unused')
    assert ddns_updater.main(['--config-file', str(path), '--dry-run']) == 2
    assert not calls


@pytest.mark.parametrize('dry', [False, True])
def test_dnsmax_cli_unavailable_blocks_all_services(monkeypatch, tmp_path, capsys, dry):
    monkeypatch.chdir(tmp_path)
    path = tmp_path/'config.ini'
    path.write_text('[first]\nddns_provider=CloudNS\napi_key='+SECRET+'\nhostname=home.example.net\n'+
        '[retired]\nddns_provider=DNSMax\nusername=user\npassword='+SECRET+'\nhostname=home.example.net')
    calls, _ = mock_http(monkeypatch, 'unused')
    assert ddns_updater.main(['--dry-run'] if dry else []) == 2
    output = capsys.readouterr()
    assert 'unavailable' in output.err
    assert SECRET not in output.out+output.err
    assert not calls
    assert not (tmp_path/'ddns_update.log').exists()


def test_dnsmax_direct_calls_never_request():
    with pytest.raises(ProviderError, match='unavailable'):
        DNSMax('service', {'username': 'user', 'password': SECRET, 'hostname': 'example.net'})
    adapter = DNSMax.__new__(DNSMax)
    with pytest.raises(ProviderError, match='unavailable'):
        adapter.update_ddns()
