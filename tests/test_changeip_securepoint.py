import pytest
import requests

import ddns_updater
from providers.ddns_provider import ProviderError
from providers.provider_changeip import ChangeIP
from providers.provider_securepoint import SecurePoint

IP = "203.0.113.42"
SECRET = "secret&%+?"
CONFIG = {"username": "user", "password": SECRET, "hostname": "test.example.net"}


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


def setup(monkeypatch, body, status=200):
    replies = [Response(IP), Response(body, status)]
    calls = []
    def get(url, **options):
        calls.append((url, options))
        return replies[len(calls)-1]
    monkeypatch.setattr(requests, "get", get)
    return calls, replies


@pytest.mark.parametrize("cls,body", [(ChangeIP, "200 Successful Update"),
    (ChangeIP, f"200 Successful Update (Address Used: {IP})\nUpdated 1 host records"),
    (SecurePoint, "good"), (SecurePoint, "nochg"),
    (SecurePoint, f"good {IP}"), (SecurePoint, f"nochg {IP}\n")])
def test_conservative_acceptance_and_request_contract(monkeypatch, cls, body):
    calls, replies = setup(monkeypatch, body)
    assert cls("service", CONFIG).update_ddns() is True
    url, options = calls[1]
    assert url == ("https://nic.changeip.com/nic/update" if cls is ChangeIP else "https://update.spdyn.de/nic/update")
    assert options["params"] == {"hostname": CONFIG["hostname"], "myip": IP}
    assert options["auth"] == (CONFIG["username"], SECRET)
    assert options["timeout"] == (5, 15)
    assert options["allow_redirects"] is False
    prepared = requests.Request("GET", url, params=options["params"], auth=options["auth"]).prepare()
    assert SECRET not in prepared.url
    assert prepared.headers["Authorization"].startswith("Basic ")
    assert all(r.closed for r in replies)


@pytest.mark.parametrize("body", ["", "OK", "not OK", "402 Premium required",
    "error: 200 Successful Update", "<html>200 Successful Update</html>",
    "200 Successful Update extra", "200 Successful Update (Address Used: 203.0.113.1)",
    "200 Successful Update (Address Used: 999.1.1.1)", "nochg"])
def test_changeip_rejects_unknown_error_and_wrong_ip(monkeypatch, body):
    _, replies = setup(monkeypatch, body)
    with pytest.raises(ProviderError):
        ChangeIP("service", CONFIG).update_ddns()
    assert all(r.closed for r in replies)


@pytest.mark.parametrize("body", ["", "badauth", "nohost", "abuse", "911",
    "not good", "goodish", "<html>good</html>", "good 203.0.113.1", "nochg ::1",
    f"good {IP} extra", f"good {IP}\nnochg {IP}"])
def test_securepoint_rejects_unknown_error_and_wrong_ip(monkeypatch, body):
    _, replies = setup(monkeypatch, body)
    with pytest.raises(ProviderError):
        SecurePoint("service", CONFIG).update_ddns()
    assert all(r.closed for r in replies)


@pytest.mark.parametrize("cls", [ChangeIP, SecurePoint])
@pytest.mark.parametrize("status", [302, 401, 500])
def test_http_failure(monkeypatch, cls, status):
    _, replies = setup(monkeypatch, SECRET, status)
    with pytest.raises(ProviderError) as error:
        cls("service", CONFIG).update_ddns()
    assert SECRET not in str(error.value)
    assert all(r.closed for r in replies)


@pytest.mark.parametrize("cls", [ChangeIP, SecurePoint])
def test_request_failure_sanitized_and_not_retried(monkeypatch, cls):
    calls, _ = setup(monkeypatch, "unused")
    provider = cls("service", CONFIG)
    failures = []
    def fail(*a, **k):
        failures.append(1)
        raise requests.Timeout(SECRET)
    monkeypatch.setattr(requests, "get", fail)
    with pytest.raises(ProviderError) as error:
        provider.update_ddns()
    assert SECRET not in str(error.value)
    assert len(failures) == 1
    assert len(calls) == 1


@pytest.mark.parametrize("cls", [ChangeIP, SecurePoint])
@pytest.mark.parametrize("accepted", [True, False])
def test_cli_status_and_redaction(monkeypatch, tmp_path, capsys, cls, accepted):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.ini").write_text("[service]\nddns_provider=" + cls.__name__ + "\n" +
        "\n".join(f"{k}={v}" for k, v in CONFIG.items()))
    success = "200 Successful Update" if cls is ChangeIP else "nochg"
    calls, _ = setup(monkeypatch, success if accepted else "error " + SECRET)
    args = ["--no-log"]
    if cls in (SecurePoint, ChangeIP):
        args += ["--state-file", str(tmp_path / "state.json"), "--refresh-seconds", "86400"]
    assert ddns_updater.main(args) == (0 if accepted else 1)
    output = capsys.readouterr()
    assert SECRET not in output.out + output.err
    assert len(calls) == 2
