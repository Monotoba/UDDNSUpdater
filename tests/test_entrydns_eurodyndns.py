import pytest
import requests

import ddns_updater
from providers.ddns_provider import ProviderError
from providers.provider_entrydns import EntryDNS
from providers.provider_eurodyndns import EuroDynDNS

IP = '203.0.113.42'
SECRET = 'secret%&+/?'
ENTRY = {'token': SECRET, 'hostname': 'example.entrydns.org'}
EURO = {'username': 'user', 'password': SECRET, 'hostname': 'example.net'}


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


@pytest.mark.parametrize('cls,config,body', [(EntryDNS, ENTRY, 'OK\n'),
    (EuroDynDNS, EURO, 'good'), (EuroDynDNS, EURO, 'nochg'),
    (EuroDynDNS, EURO, 'good '+IP), (EuroDynDNS, EURO, 'nochg '+IP)])
def test_requests_and_acceptance(monkeypatch, cls, config, body):
    calls, replies = mock_http(monkeypatch, body)
    assert cls('service', config).update_ddns() is True
    url, options = calls[1]
    if cls is EntryDNS:
        assert url == 'https://entrydns.net/records/modify/secret%25%26%2B%2F%3F'
        assert options['params'] == {'ip': IP}
        assert 'auth' not in options
    else:
        assert url == 'https://update.eurodyndns.org/update/'
        assert options['params'] == {'hostname': EURO['hostname'], 'myip': IP}
        assert options['auth'] == ('user', SECRET)
    assert options['timeout'] == (5, 15)
    assert options['allow_redirects'] is False
    assert options.get('verify', True) is True
    assert all(reply.closed for reply in replies)


@pytest.mark.parametrize('body', ['', 'success', 'OK wrong', 'not OK', 'ok', '<html>OK</html>',
    'OK\nrejected', SECRET])
def test_entrydns_bad_body(monkeypatch, body):
    _, replies = mock_http(monkeypatch, body)
    with pytest.raises(ProviderError) as error:
        EntryDNS('service', ENTRY).update_ddns()
    assert SECRET not in str(error.value)
    assert all(reply.closed for reply in replies)


@pytest.mark.parametrize('body', ['', 'not good', 'goodish', 'nochgish', 'abuse', 'badauth', '!yours',
    'notfqdn', 'nohost', 'numhost', 'dnserr', '<html>good</html>', 'good 203.0.113.43',
    'good '+IP+' extra', 'good\n'+IP, 'good\nnochg', SECRET])
def test_eurodyndns_bad_body(monkeypatch, body):
    _, replies = mock_http(monkeypatch, body)
    with pytest.raises(ProviderError) as error:
        EuroDynDNS('service', EURO).update_ddns()
    assert SECRET not in str(error.value)
    assert all(reply.closed for reply in replies)


@pytest.mark.parametrize('cls,config', [(EntryDNS, ENTRY), (EuroDynDNS, EURO)])
@pytest.mark.parametrize('status', [204, 301, 400, 401, 403, 404, 500])
def test_http_failure(monkeypatch, cls, config, status):
    _, replies = mock_http(monkeypatch, SECRET, status)
    with pytest.raises(ProviderError) as error:
        cls('service', config).update_ddns()
    assert SECRET not in str(error.value)
    assert all(reply.closed for reply in replies)


@pytest.mark.parametrize('cls,config', [(EntryDNS, ENTRY), (EuroDynDNS, EURO)])
def test_timeout_no_retry_and_sanitized(monkeypatch, cls, config):
    mock_http(monkeypatch, 'unused')
    adapter = cls('service', config)
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        raise requests.Timeout('URL with '+SECRET)
    monkeypatch.setattr(requests, 'get', fail)
    with pytest.raises(ProviderError) as error:
        adapter.update_ddns()
    assert SECRET not in str(error.value)
    assert len(calls) == 1


@pytest.mark.parametrize('cls,config', [(EntryDNS, ENTRY), (EuroDynDNS, EURO)])
@pytest.mark.parametrize('ip', ['bad', '2001:db8::1'])
def test_invalid_ipv4_prevents_update(monkeypatch, cls, config, ip):
    mock_http(monkeypatch, 'unused')
    adapter = cls('service', config)
    adapter.external_ip = ip
    calls, _ = mock_http(monkeypatch, 'unused')
    with pytest.raises(ProviderError):
        adapter.update_ddns()
    assert not calls


@pytest.mark.parametrize('token', ['.', '..'])
def test_entrydns_dot_segment_token_before_discovery(monkeypatch, token):
    calls, _ = mock_http(monkeypatch, 'unused')
    with pytest.raises(ProviderError):
        EntryDNS('service', dict(ENTRY, token=token))
    assert not calls


@pytest.mark.parametrize('cls,config,body', [(EntryDNS, ENTRY, 'OK'), (EuroDynDNS, EURO, 'good')])
@pytest.mark.parametrize('accepted', [False, True])
def test_cli_reports_acceptance_or_failure(monkeypatch, tmp_path, capsys, cls, config, body, accepted):
    path = tmp_path/'config.ini'
    path.write_text('[service]\nddns_provider='+cls.__name__+'\n'+
        '\n'.join(f'{k}={v}' for k,v in config.items()))
    mock_http(monkeypatch, body if accepted else 'rejected '+SECRET)
    assert ddns_updater.main(['--config-file', str(path), '--no-log']) == (0 if accepted else 1)
    output = capsys.readouterr()
    assert SECRET not in output.out+output.err
    assert ('provider accepted' in output.out) == accepted


def test_entrydns_old_password_configuration_rejected(monkeypatch, tmp_path):
    path = tmp_path/'config.ini'
    path.write_text('[service]\nddns_provider=EntryDNS\nusername=user\npassword='+SECRET+'\nhostname=example.entrydns.org')
    calls, _ = mock_http(monkeypatch, 'unused')
    assert ddns_updater.main(['--config-file', str(path), '--dry-run']) == 2
    assert not calls
