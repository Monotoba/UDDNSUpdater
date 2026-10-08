import pytest
import requests

import ddns_updater
from providers.ddns_provider import ProviderError
from providers.provider_godaddy import GoDaddyDDNS
from providers.provider_googledomains import GoogleDomains

IP = "203.0.113.42"
SECRET = "secret%&+?"
SETTINGS = {"api_key": "key", "api_secret": SECRET, "domain": "example.net", "hostname": "@"}


@pytest.fixture(autouse=True)
def prohibit_network(monkeypatch):
    def fail(*a, **k):
        pytest.fail("Real HTTP prohibited")
    monkeypatch.setattr(requests.sessions.Session, "request", fail)


class Response:
    def __init__(self, text, status=200):
        self.text, self.status_code, self.closed = text, status, False
    def close(self):
        self.closed = True


def mock_http(monkeypatch, status=200, body=""):
    discovery, update = Response(IP), Response(body, status)
    calls = []
    monkeypatch.setattr(requests, "get", lambda *a, **k: discovery)
    def put(url, **options):
        calls.append((url, options))
        return update
    monkeypatch.setattr(requests, "put", put)
    return calls, discovery, update


@pytest.mark.parametrize("status", [200, 204])
@pytest.mark.parametrize("hostname,encoded", [("@", "%40"), ("www", "www"), ("*", "%2A")])
def test_godaddy_scoped_put_and_empty_acceptance(monkeypatch, status, hostname, encoded):
    calls, discovery, update = mock_http(monkeypatch, status)
    provider = GoDaddyDDNS("service", dict(SETTINGS, hostname=hostname))
    assert provider.update_ddns() is True
    url, options = calls[0]
    assert url == "https://api.godaddy.com/v1/domains/example.net/records/A/" + encoded
    assert options["json"] == [{"data": IP, "ttl": 600}]
    assert options["headers"]["Authorization"] == "sso-key key:" + SECRET
    assert SECRET not in url
    assert options["timeout"] == (5, 15)
    assert options["allow_redirects"] is False
    assert discovery.closed and update.closed


@pytest.mark.parametrize("status", [201, 202, 302, 400, 401, 403, 404, 429, 500])
def test_godaddy_http_errors(monkeypatch, status):
    _, _, update = mock_http(monkeypatch, status, SECRET)
    with pytest.raises(ProviderError) as error:
        GoDaddyDDNS("service", SETTINGS).update_ddns()
    assert SECRET not in str(error.value)
    assert update.closed


def test_godaddy_unexpected_body_fails(monkeypatch):
    mock_http(monkeypatch, 200, '{"error":"' + SECRET + '"}')
    with pytest.raises(ProviderError) as error:
        GoDaddyDDNS("service", SETTINGS).update_ddns()
    assert SECRET not in str(error.value)


def test_godaddy_timeout_no_retry(monkeypatch):
    mock_http(monkeypatch)
    calls = []
    def fail(*a, **k):
        calls.append(1)
        raise requests.Timeout(SECRET)
    monkeypatch.setattr(requests, "put", fail)
    with pytest.raises(ProviderError) as error:
        GoDaddyDDNS("service", SETTINGS).update_ddns()
    assert SECRET not in str(error.value)
    assert len(calls) == 1


@pytest.mark.parametrize("key,value", [("api_secret", "bad\r\nHeader: secret"), ("hostname", ".."), ("domain", ".")])
def test_godaddy_invalid_header_or_target_prevents_put(monkeypatch, key, value):
    calls, _, _ = mock_http(monkeypatch)
    with pytest.raises(ProviderError):
        GoDaddyDDNS("service", dict(SETTINGS, **{key:value})).update_ddns()
    assert not calls


def test_godaddy_missing_record_name_fails_config_before_requests(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.ini").write_text("[service]\nddns_provider=GoDaddyDDNS\napi_key=key\napi_secret=secret\ndomain=example.net\n")
    assert ddns_updater.main([]) == 2
    assert not (tmp_path / "ddns_update.log").exists()


@pytest.mark.parametrize("dry", [False, True])
def test_google_cli_unavailable_before_requests(tmp_path, monkeypatch, capsys, dry):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.ini").write_text("[service]\nddns_provider=GoogleDomains\napi_key="+SECRET+"\nhostname=example.net\n")
    assert ddns_updater.main(["--dry-run"] if dry else []) == 2
    output = capsys.readouterr()
    assert "unavailable" in output.err
    assert SECRET not in output.out + output.err
    assert not (tmp_path / "ddns_update.log").exists()


def test_google_direct_calls_never_contact_service():
    with pytest.raises(ProviderError, match="unavailable"):
        GoogleDomains("service", {"api_key":SECRET, "hostname":"example.net"})
    instance = object.__new__(GoogleDomains)
    with pytest.raises(ProviderError, match="unavailable"):
        instance.update_ddns()
