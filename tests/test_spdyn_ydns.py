import pytest
import requests

import ddns_updater
from providers.ddns_provider import ProviderError
from providers.provider_spdyn import SpDYN
from providers.provider_ydns import YDNS

IP = "203.0.113.42"
SECRET = "secret%&+?"
CONFIG = {"hostname": "example.ydns.io", "username": "api-user", "password": SECRET}


@pytest.fixture(autouse=True)
def prohibit_http(monkeypatch):
    def fail(*a, **k):
        pytest.fail("Real HTTP prohibited")
    monkeypatch.setattr(requests.sessions.Session, "request", fail)


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
    monkeypatch.setattr(requests, "get", get)
    return calls, replies


@pytest.mark.parametrize("cls,body", [(YDNS, "good\n"), (SpDYN, "good"), (SpDYN, "nochg"), (SpDYN, f"good {IP}")])
def test_request_and_acceptance(monkeypatch, cls, body):
    calls, replies = mock_http(monkeypatch, body)
    assert cls("service", CONFIG).update_ddns() is True
    url, options = calls[1]
    assert url == ("https://ydns.io/api/v1/update/" if cls is YDNS else "https://update.spdyn.de/nic/update")
    assert options["params"] == ({"host": CONFIG["hostname"], "ip": IP} if cls is YDNS else
                                 {"hostname": CONFIG["hostname"], "myip": IP})
    assert options["auth"] == (CONFIG["username"], SECRET)
    assert options["timeout"] == (5, 15)
    assert options["allow_redirects"] is False
    assert all(r.closed for r in replies)


@pytest.mark.parametrize("cls", [YDNS, SpDYN])
@pytest.mark.parametrize("body", ["", "not good", "goodish", "badauth", "<html>good</html>", "good wrong"])
def test_bad_bodies_fail(monkeypatch, cls, body):
    _, replies = mock_http(monkeypatch, body)
    with pytest.raises(ProviderError):
        cls("service", CONFIG).update_ddns()
    assert all(r.closed for r in replies)


@pytest.mark.parametrize("status", [301, 400, 401, 404, 500])
def test_ydns_http_failure(monkeypatch, status):
    _, replies = mock_http(monkeypatch, SECRET, status)
    with pytest.raises(ProviderError) as error:
        YDNS("service", CONFIG).update_ddns()
    assert SECRET not in str(error.value)
    assert all(r.closed for r in replies)


def test_legacy_ydns_aliases_need_api_username(monkeypatch):
    calls, _ = mock_http(monkeypatch, "good")
    legacy = {"domain_id": "example.ydns.io", "api_key": SECRET, "api_username": "api-user"}
    provider = YDNS("service", legacy)
    assert provider.domain_id == legacy["domain_id"]
    assert provider.api_key == SECRET
    assert provider.update_ddns() is True
    assert calls[1][1]["auth"] == ("api-user", SECRET)


def test_preferred_keys_override_legacy_aliases():
    config = dict(CONFIG, domain_id="wrong", api_key="wrong", api_username="wrong")
    normalized = YDNS.normalize_settings(config)
    assert all(normalized[key] == value for key, value in CONFIG.items())
    assert normalized["api_key"] == "wrong"


@pytest.mark.parametrize("settings", [{"domain_id": "1234", "api_key": SECRET, "api_username": "user"},
                                      {"domain_id": "example.ydns.io", "api_key": SECRET}])
def test_invalid_legacy_settings_prevent_requests(monkeypatch, settings):
    calls, _ = mock_http(monkeypatch, "unused")
    with pytest.raises(ProviderError):
        YDNS("service", settings)
    assert not calls


@pytest.mark.parametrize("legacy,expected", [(False, 0), (True, 0), ("missing-user", 2), ("numeric", 2)])
def test_cli_normalizes_before_dry_run(monkeypatch, tmp_path, legacy, expected):
    monkeypatch.chdir(tmp_path)
    settings = CONFIG if not legacy else {"domain_id": "example.ydns.io", "api_key": SECRET, "api_username": "api-user"}
    if legacy == "missing-user":
        settings.pop("api_username")
    if legacy == "numeric":
        settings["domain_id"] = "1234"
    path = tmp_path / "config.ini"
    path.write_text("[service]\nddns_provider=YDNS\n" + "\n".join(f"{k}={v}" for k,v in settings.items()))
    calls, _ = mock_http(monkeypatch, "unused")
    assert ddns_updater.main(["--dry-run"]) == expected
    assert not calls
    assert not (tmp_path / "ddns_update.log").exists()


@pytest.mark.parametrize("cls", [YDNS, SpDYN])
def test_cli_rejection_has_failure_status(monkeypatch, tmp_path, capsys, cls):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.ini").write_text("[service]\nddns_provider="+cls.__name__+"\n"+
        "\n".join(f"{k}={v}" for k,v in CONFIG.items()))
    mock_http(monkeypatch, "rejected " + SECRET)
    args = ["--no-log"]
    if cls is SpDYN:
        args += ["--state-file", str(tmp_path / "state.json"), "--refresh-seconds", "86400"]
    assert ddns_updater.main(args) == 1
    output = capsys.readouterr()
    assert SECRET not in output.out + output.err
