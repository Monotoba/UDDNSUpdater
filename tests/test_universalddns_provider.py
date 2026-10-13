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
    assert [item[0] for item in calls] == ["GET", "PUT", "GET", "GET"]
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
