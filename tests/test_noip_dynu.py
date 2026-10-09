from urllib.parse import parse_qs, urlsplit

import pytest
import requests

import ddns_updater
from providers.ddns_provider import ProviderError
from providers.provider_noip import NoIP
from providers.provider_dynu import Dynu

IP = "203.0.113.42"
SECRET = "secret&%+?"
SETTINGS = {"username": "user@example.net", "password": SECRET, "hostname": "test.example.net"}


@pytest.fixture(autouse=True)
def prohibit_http(monkeypatch):
    def blocked(*a, **k):
        pytest.fail("Real HTTP prohibited")
    monkeypatch.setattr(requests.sessions.Session, "request", blocked)


class Response:
    def __init__(self, text, status=200):
        self.text, self.status_code, self.closed = text, status, False
    def close(self):
        self.closed = True


def mock_http(monkeypatch, body, status=200):
    replies = [Response(IP), Response(body, status)]
    calls = []
    def get(url, **options):
        calls.append((url, options))
        return replies[len(calls) - 1]
    monkeypatch.setattr(requests, "get", get)
    return calls, replies


@pytest.mark.parametrize("cls", [NoIP, Dynu])
@pytest.mark.parametrize("code", ["good", "nochg"])
def test_accepted_response_auth_encoding_and_closure(monkeypatch, cls, code):
    calls, replies = mock_http(monkeypatch, f"{code} {IP}\n")
    provider = cls("service", SETTINGS)
    assert provider.update_ddns() is True
    url, options = calls[1]
    assert url == ("https://dynupdate.no-ip.com/nic/update" if cls is NoIP else "https://api.dynu.com/nic/update")
    assert options["auth"] == (SETTINGS["username"], SECRET)
    assert options["timeout"] == (5, 15)
    assert options["allow_redirects"] is False
    assert options["params"]["hostname"] == SETTINGS["hostname"]
    assert options["params"]["myip"] == IP
    prepared = requests.Request("GET", url, params=options["params"], auth=options["auth"]).prepare()
    assert SECRET not in prepared.url
    assert "password" not in parse_qs(urlsplit(prepared.url).query)
    assert prepared.headers["Authorization"].startswith("Basic ")
    if cls is NoIP:
        assert options["headers"]["User-Agent"].startswith("Monotoba UDDNSUpdater/")
    else:
        assert options["params"]["myipv6"] == "no"
    assert all(r.closed for r in replies)


@pytest.mark.parametrize("code", ["good", "nochg"])
def test_dynu_accepts_bare_documented_status(monkeypatch, code):
    mock_http(monkeypatch, code)
    assert Dynu("service", SETTINGS).update_ddns() is True


@pytest.mark.parametrize("cls", [NoIP, Dynu])
@pytest.mark.parametrize("body", ["", "badauth", "nohost", "abuse", "911", "badagent", "!donator",
                                 "servererror", "dnserr", "goodish", "not good", "<html>good</html>",
                                 "good 203.0.113.1", "nochg ::1", "good 999.1.1.1", "good 203.0.113.42 extra"])
def test_rejections_and_malformed_responses_are_failures(monkeypatch, cls, body):
    calls, replies = mock_http(monkeypatch, body)
    with pytest.raises(ProviderError) as error:
        cls("service", SETTINGS).update_ddns()
    assert SECRET not in str(error.value)
    assert len(calls) == 2
    assert all(r.closed for r in replies)


@pytest.mark.parametrize("body", ["good", "nochg", f"good {IP}\nnochg {IP}"])
def test_noip_requires_one_ip_result_per_host(monkeypatch, body):
    mock_http(monkeypatch, body)
    with pytest.raises(ProviderError):
        NoIP("service", SETTINGS).update_ddns()


@pytest.mark.parametrize("body,accepted", [(f"good {IP}\nnochg {IP}\n", True),
                                          (f"good {IP}", False),
                                          (f"good {IP}\nbadauth", False)])
def test_noip_multi_host_results(monkeypatch, body, accepted):
    calls, _ = mock_http(monkeypatch, body)
    provider = NoIP("service", dict(SETTINGS, hostname="one.example.net,two.example.net"))
    if accepted:
        assert provider.update_ddns() is True
    else:
        with pytest.raises(ProviderError):
            provider.update_ddns()
    assert calls[1][1]["params"]["hostname"] == "one.example.net,two.example.net"


@pytest.mark.parametrize("agent", ["", "bad\r\nSecret: " + SECRET, "bad\x00", "nonascii-\u2603"])
def test_invalid_user_agent_prevents_update(monkeypatch, agent):
    calls, _ = mock_http(monkeypatch, "unused")
    provider = NoIP("service", dict(SETTINGS, user_agent=agent))
    with pytest.raises(ProviderError):
        provider.update_ddns()
    assert len(calls) == 1


def test_custom_noip_agent(monkeypatch):
    calls, _ = mock_http(monkeypatch, f"good {IP}")
    agent = "Example UDDNSUpdater/Linux-development maintainer@example.net"
    assert NoIP("service", dict(SETTINGS, user_agent=agent)).update_ddns() is True
    assert calls[1][1]["headers"] == {"User-Agent": agent}


@pytest.mark.parametrize("hostname", [",", "one,", ",two", "one, ,two"])
def test_empty_noip_hosts_prevent_update(monkeypatch, hostname):
    calls, _ = mock_http(monkeypatch, "unused")
    with pytest.raises(ProviderError):
        NoIP("service", dict(SETTINGS, hostname=hostname)).update_ddns()
    assert len(calls) == 1


@pytest.mark.parametrize("cls", [NoIP, Dynu])
@pytest.mark.parametrize("status", [302, 401, 500])
def test_update_http_errors_not_accepted(monkeypatch, cls, status):
    _, replies = mock_http(monkeypatch, SECRET, status)
    with pytest.raises(ProviderError):
        cls("service", SETTINGS).update_ddns()
    assert all(r.closed for r in replies)


@pytest.mark.parametrize("cls", [NoIP, Dynu])
def test_update_network_error_sanitized(monkeypatch, cls):
    calls, _ = mock_http(monkeypatch, "unused")
    provider = cls("service", SETTINGS)
    def fail(*a, **k):
        raise requests.Timeout(SECRET)
    monkeypatch.setattr(requests, "get", fail)
    with pytest.raises(ProviderError) as error:
        provider.update_ddns()
    assert SECRET not in str(error.value)
    assert len(calls) == 1


@pytest.mark.parametrize("cls", [NoIP, Dynu])
@pytest.mark.parametrize("accepted", [True, False])
def test_cli_returns_correct_status_without_secrets(monkeypatch, tmp_path, capsys, cls, accepted):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.ini").write_text("[service]\nddns_provider=" + cls.__name__ + "\n" +
        "\n".join(f"{k}={v}" for k, v in SETTINGS.items()))
    calls, _ = mock_http(monkeypatch, f"nochg {IP}" if accepted else "badauth " + SECRET)
    args = ["--no-log"]
    args += ["--state-file", str(tmp_path / "state.json"), "--refresh-seconds", "86400"]
    assert ddns_updater.main(args) == (0 if accepted else 1)
    output = capsys.readouterr()
    assert SECRET not in output.out + output.err
    assert len(calls) == 2  # No automatic retries, including provider rejections.
