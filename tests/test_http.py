from urllib.parse import parse_qs, urlsplit

import pytest
import requests

import ddns_updater
from providers.ddns_provider import DDNSProvider, ProviderError
from providers.provider_namecheap import NamecheapDDNS
from providers.provider_duckddns import DuckDNS

IP = "203.0.113.42"
SECRET = "secret&token=%+?"
SUCCESS = f"<interface-response><IP>{IP}</IP><ErrCount>0</ErrCount><errors/><Done>true</Done></interface-response>"
SETTINGS = {NamecheapDDNS: {"domain": "Example.net", "hostname": "@", "password": SECRET},
            DuckDNS: {"subdomain": "one,two", "token": SECRET}}


@pytest.fixture(autouse=True)
def prohibit_network(monkeypatch):
    def blocked(*a, **k):
        pytest.fail("Real HTTP prohibited")
    monkeypatch.setattr(requests.sessions.Session, "request", blocked)


class Response:
    def __init__(self, text, status=200):
        self.text = text
        self.status_code = status
        self.closed = False
    def close(self):
        self.closed = True


def responses(monkeypatch, items):
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        item = items[len(calls) - 1]
        if isinstance(item, Exception):
            raise item
        return item
    monkeypatch.setattr(requests, "get", get)
    return calls


@pytest.mark.parametrize("cls,body", [(NamecheapDDNS, SUCCESS), (DuckDNS, "OK\n")])
def test_request_contract_encoded_secrets_and_closed_responses(monkeypatch, cls, body):
    discovery, update = Response(IP + "\n"), Response(body)
    calls = responses(monkeypatch, [discovery, update])
    provider = cls("service", SETTINGS[cls])
    assert provider.update_ddns() is True
    assert calls[0][0] == "https://api.ipify.org"
    endpoint = ("https://dynamicdns.park-your-domain.com/update" if cls is NamecheapDDNS
                else "https://www.duckdns.org/update")
    assert calls[1][0] == endpoint
    for url, kwargs in calls:
        assert kwargs["timeout"] == (5, 15)
        assert kwargs["allow_redirects"] is False
        assert SECRET not in url
    params = calls[1][1]["params"]
    assert params["ip"] == IP
    key = "password" if cls is NamecheapDDNS else "token"
    prepared = requests.Request("GET", endpoint, params=params).prepare()
    assert parse_qs(urlsplit(prepared.url).query)[key] == [SECRET]
    assert discovery.closed and update.closed


@pytest.mark.parametrize("body", ["", "<html>hello</html>", "::1", "999.1.2.3", "1.2.3.4 extra", "01.2.3.4"])
def test_invalid_discovery_prevents_provider_update(monkeypatch, body):
    response = Response(body)
    calls = responses(monkeypatch, [response])
    with pytest.raises(ProviderError, match="Invalid IPv4"):
        NamecheapDDNS("service", SETTINGS[NamecheapDDNS])
    assert len(calls) == 1
    assert response.closed


@pytest.mark.parametrize("status", [201, 204, 301, 302, 307, 400, 401, 500])
def test_http_failures_including_redirects(monkeypatch, status):
    response = Response(SECRET, status)
    responses(monkeypatch, [response])
    with pytest.raises(ProviderError) as error:
        DDNSProvider("service", {})
    assert SECRET not in str(error.value)
    assert response.closed


@pytest.mark.parametrize("error_type", [requests.Timeout, requests.ConnectionError, requests.HTTPError])
def test_request_exceptions_are_sanitized(monkeypatch, error_type):
    responses(monkeypatch, [error_type("https://example.net/?token=" + SECRET)])
    with pytest.raises(ProviderError) as error:
        DDNSProvider("service", {})
    assert SECRET not in str(error.value)
    assert error.value.__suppress_context__


def test_parsing_limit_closes_response(monkeypatch):
    response = Response("x" * (DDNSProvider.max_response_chars + 1))
    responses(monkeypatch, [response])
    with pytest.raises(ProviderError, match="parsing limit"):
        DDNSProvider("service", {})
    assert response.closed


def test_close_failure_is_sanitized(monkeypatch):
    response = Response(IP)
    def close():
        raise requests.ConnectionError(SECRET)
    response.close = close
    responses(monkeypatch, [response])
    with pytest.raises(ProviderError) as error:
        DDNSProvider("service", {})
    assert SECRET not in str(error.value)


@pytest.mark.parametrize("cls", SETTINGS)
def test_update_http_failure_rejected(monkeypatch, cls):
    response = Response(SECRET, 302)
    responses(monkeypatch, [Response(IP), response])
    provider = cls("service", SETTINGS[cls])
    with pytest.raises(ProviderError):
        provider.update_ddns()
    assert response.closed


@pytest.mark.parametrize("cls", SETTINGS)
def test_missing_direct_call_credentials_prevent_network(monkeypatch, cls):
    calls = responses(monkeypatch, [])
    with pytest.raises(ProviderError):
        cls("service", {})
    assert not calls


@pytest.mark.parametrize("body", [
    "", "<html>bad</html>", "<broken", SUCCESS.replace("<ErrCount>0", "<ErrCount>1"),
    SUCCESS.replace("<Done>true", "<Done>false"), SUCCESS.replace(IP, "203.0.113.1"),
    SUCCESS.replace("<IP>" + IP + "</IP>", ""),
    SUCCESS.replace("<ErrCount>0</ErrCount>", "<ErrCount>0</ErrCount><ErrCount>0</ErrCount>"),
    SUCCESS.replace("<errors/>", "<errors><Err1>" + SECRET + "</Err1></errors>"),
    SUCCESS.replace("<errors/>", "<Errors>rejected</Errors>"),
    "<!DOCTYPE interface-response [<!ENTITY x 'bad'>]>" + SUCCESS,
], ids=["empty", "html", "malformed", "errcount", "not-done", "wrong-ip", "no-ip", "duplicate", "errors", "Errors", "doctype"])
def test_namecheap_rejects_unconfirmed_responses(monkeypatch, body):
    update = Response(body)
    responses(monkeypatch, [Response(IP), update])
    provider = NamecheapDDNS("service", SETTINGS[NamecheapDDNS])
    with pytest.raises(ProviderError) as error:
        provider.update_ddns()
    assert SECRET not in str(error.value)
    assert update.closed


def test_namecheap_unicode_xml_ignores_misdeclared_encoding(monkeypatch):
    responses(monkeypatch, [Response(IP), Response('<?xml version="1.0" encoding="utf-16"?>' + SUCCESS)])
    assert NamecheapDDNS("service", SETTINGS[NamecheapDDNS]).update_ddns() is True


@pytest.mark.parametrize("body", ["KO", "", "okay", "OK extra", "OK\n" + IP, "<html>OK</html>"])
def test_duckdns_rejects_non_ok_body(monkeypatch, body):
    responses(monkeypatch, [Response(IP), Response(body)])
    with pytest.raises(ProviderError):
        DuckDNS("service", SETTINGS[DuckDNS]).update_ddns()


@pytest.mark.parametrize("cls", SETTINGS)
def test_invalid_mutated_ip_is_rejected_before_update(monkeypatch, cls):
    calls = responses(monkeypatch, [Response(IP)])
    provider = cls("service", SETTINGS[cls])
    provider.external_ip = "bad"
    with pytest.raises(ProviderError):
        provider.update_ddns()
    assert len(calls) == 1


@pytest.mark.parametrize("accepted", [True, False])
@pytest.mark.parametrize("cls", SETTINGS)
def test_real_cli_reports_acceptance_or_failure(monkeypatch, tmp_path, capsys, accepted, cls):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "config.ini"
    config.write_text("[service]\nddns_provider=" + cls.__name__ + "\n" +
                      "\n".join(f"{key}={value}" for key, value in SETTINGS[cls].items()))
    body = (SUCCESS if cls is NamecheapDDNS else "OK") if accepted else "KO " + SECRET
    responses(monkeypatch, [Response(IP), Response(body)])
    assert ddns_updater.main(["--no-log"]) == (0 if accepted else 1)
    output = capsys.readouterr()
    assert SECRET not in output.out + output.err
    if accepted:
        assert "provider accepted" in output.out
        assert "propagation is unverified" in output.out
    else:
        assert "update failed" in output.err
