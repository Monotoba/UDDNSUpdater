import json
import uuid

import pytest

from providers.provider_universalddns import UniversalDDNSServer
from providers.ddns_provider import ProviderError, ProviderStopError


class Response:
    def __init__(self, body, status):
        self.text = json.dumps(body)
        self.status_code = status
        self.closed = False
    def close(self):
        self.closed = True


def test_accepted_intent_must_reach_applied(monkeypatch):
    import requests
    identifier = str(uuid.uuid4())
    calls = []
    items = [
        Response("192.0.2.30", 200),
        Response({"intent_id": identifier, "status": "pending"}, 202),
        Response({"intent_id": identifier, "status": "pending"}, 200),
        Response({"intent_id": identifier, "status": "applied"}, 200),
    ]
    def fake_request(self, method, url, **kwargs):
        calls.append((method, url, kwargs))
        return items.pop(0)
    monkeypatch.setattr(requests.sessions.Session, "request", fake_request)
    # Supply discovery response as raw text rather than JSON.
    items[0].text = "192.0.2.30"
    config = {"base_url": "http://127.0.0.1:8765",
              "record_id": "home", "token": "x" * 48}
    provider = UniversalDDNSServer("local", config)
    assert provider.update_ddns() is True
    assert [item[0].upper() for item in calls] == ["GET", "PUT", "GET", "GET"]
    assert calls[1][2]["json"]["address"] == "192.0.2.30"
    assert calls[1][2]["allow_redirects"] is False
    assert calls[1][2]["headers"]["Authorization"].startswith("Bearer ")
    assert not items


def test_unconfirmed_is_not_success(monkeypatch):
    import requests
    identifier = str(uuid.uuid4())
    responses = [Response("192.0.2.30", 200),
                 Response({"intent_id": identifier, "status": "pending"}, 202)]
    responses[0].text = "192.0.2.30"
    responses += [Response({"intent_id": identifier, "status": "pending"}, 200)
                  for _ in range(3)]
    monkeypatch.setattr(requests.sessions.Session, "request",
                        lambda *args, **kwargs: responses.pop(0))
    provider = UniversalDDNSServer("local", {
        "base_url": "http://localhost:8765", "record_id": "home",
        "token": "x" * 48,
    })
    with pytest.raises(ProviderStopError, match="still pending"):
        provider.update_ddns()


@pytest.mark.parametrize("endpoint", [
    "https://example.com", "http://example.com:8765",
    "http://127.0.0.1:8765@evil.example:8080",
    "http://127.0.0.1:8765/path", "http://localhost",
])
def test_invalid_endpoint_is_rejected_before_network(endpoint):
    with pytest.raises(ProviderError):
        UniversalDDNSServer("test", {"base_url": endpoint, "record_id": "home", "token": "x" * 48})

def test_restart_resumes_polling_without_second_put(monkeypatch, tmp_path):
    import requests
    from update_state import open_state
    from ddns_updater import service_state_key
    identifier = str(uuid.uuid4())
    config = {"base_url": "http://127.0.0.1:8765",
              "record_id": "home", "token": "x" * 48}
    state_key = service_state_key("local", UniversalDDNSServer, config)
    state_path = tmp_path / "state.json"
    with open_state(state_path) as state:
        state.record_pending(state_key, "192.0.2.30", identifier)
        state.save()
    calls = []
    replies = [Response({"intent_id": identifier, "status": "applied"}, 200)]
    def request(self, method, url, **kwargs):
        calls.append((method.lower(), url))
        return replies.pop(0)
    monkeypatch.setattr(requests.sessions.Session, "request", request)
    with open_state(state_path) as state:
        provider = UniversalDDNSServer.__new__(UniversalDDNSServer)
        provider.name = "local"
        provider.config = config
        provider.external_ip = "192.0.2.30"
        provider.pending_state = state
        provider.pending_state_key = state_key
        assert provider.update_ddns() is True
        assert not state.pending
    assert len(calls) == 1
    assert calls[0][0] == "get"
    assert identifier in calls[0][1]


def test_pending_survives_restart_and_rejects_changed_address(tmp_path):
    from update_state import open_state
    key = "c" * 64
    identifier = str(uuid.uuid4())
    path = tmp_path / "state.json"
    with open_state(path) as state:
        state.record_pending(key, "192.0.2.30", identifier)
        state.save()
    with open_state(path) as state:
        assert state.pending[key] == {"ipv4": "192.0.2.30", "intent_id": identifier}
        provider = UniversalDDNSServer.__new__(UniversalDDNSServer)
        provider.name = "local"
        provider.config = {"base_url": "http://127.0.0.1:8765",
                           "record_id": "home", "token": "x" * 48}
        provider.external_ip = "192.0.2.31"
        provider.pending_state = state
        provider.pending_state_key = key
        with pytest.raises(ProviderStopError, match="Unresolved earlier"):
            provider.update_ddns()

def test_cli_restart_recovers_stopped_intent_without_resubmission(monkeypatch, tmp_path):
    import requests
    import ddns_updater
    from update_state import open_state
    from ddns_updater import service_state_key
    identifier = str(uuid.uuid4())
    config = {"base_url": "http://127.0.0.1:8765", "record_id": "home",
              "token": "x" * 48}
    key = service_state_key("home", UniversalDDNSServer,
                            {"ddns_provider": "UniversalDDNSServer", **config})
    config_file = tmp_path / "config.ini"
    config_file.write_text("[home]\nddns_provider=UniversalDDNSServer\n"
                           + "\n".join(f"{k}={v}" for k, v in config.items()) + "\n")
    state_file = tmp_path / "state.json"
    with open_state(state_file) as state:
        state.record_pending(key, "192.0.2.30", identifier)
        state.record_error(ddns_updater.provider_error_key(UniversalDDNSServer, config),
                           now=100)
        state.save()
    seen = []
    def request(self, method, url, **kwargs):
        seen.append((method.upper(), url))
        if "api.ipify.org" in url:
            response = Response(None, 200)
            response.text = "192.0.2.30"
            return response
        return Response({"intent_id": identifier, "status": "applied"}, 200)
    monkeypatch.setattr(requests.sessions.Session, "request", request)
    result = ddns_updater.main(["--no-log", "--config-file", str(config_file),
                                "--state-file", str(state_file), "--refresh-seconds", "3600"])
    assert result == 0
    assert [method for method, _ in seen] == ["GET", "GET"]
    with open_state(state_file) as state:
        assert not state.pending
        assert not state.errors
        assert state.entries[key]["ipv4"] == "192.0.2.30"
