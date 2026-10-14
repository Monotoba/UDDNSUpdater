"""UniversalDDNSServer pre-alpha loopback adapter."""
import hashlib
import json
import re
from urllib.parse import urlsplit, quote

from .ddns_provider import (
    DDNSProvider, ProviderError, ProviderHTTPError, ProviderRetryError,
    ProviderStopError,
)


class UniversalDDNSServer(DDNSProvider):
    required_fields = ("base_url", "record_id", "token")
    requires_persistent_state = True
    max_polls = 3

    @staticmethod
    def validate_settings(config):
        base = config.get("base_url", "")
        try:
            parsed = urlsplit(base)
            valid = (parsed.scheme == "http" and
                     parsed.hostname in ("127.0.0.1", "localhost") and
                     parsed.port is not None and
                     not parsed.username and not parsed.password and
                     not parsed.path.rstrip("/") and not parsed.query and
                     not parsed.fragment)
        except ValueError:
            valid = False
        if not valid:
            raise ProviderError("Only explicit local loopback DDNS API endpoints are supported.")
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", config.get("record_id", "")):
            raise ProviderError("Invalid managed record identifier.")
        token = config.get("token", "")
        if len(token) < 32 or any(ord(char) < 33 or ord(char) > 126 for char in token):
            raise ProviderError("Invalid API bearer credential.")

    def __init__(self, name, config):
        self.validate_settings(config)
        super().__init__(name, config)

    @staticmethod
    def _json_object(raw):
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError
                result[key] = value
            return result
        try:
            result = json.loads(raw, object_pairs_hook=unique)
            if not isinstance(result, dict):
                raise ValueError
            return result
        except (ValueError, TypeError, RecursionError):
            raise ProviderStopError("DDNS API returned an invalid response; intervention required.") from None

    def update_ddns(self):
        self.validate_settings(self.config)
        address = self.validate_ipv4(self.external_ip)
        record_id = self.config["record_id"]
        base = self.config["base_url"].rstrip("/")
        # Stable per service/record/IP to preserve server idempotency on manual retry.
        key = hashlib.sha256(
            (self.name + "\0" + base + "\0" + record_id + "\0" + address).encode()
        ).hexdigest()
        headers = {"Authorization": "Bearer " + self.config["token"]}
        state_store = getattr(self, "pending_state", None)
        state_key = getattr(self, "pending_state_key", None)
        prior = state_store.pending.get(state_key) if state_store is not None else None
        if prior is not None and prior["ipv4"] != address:
            raise ProviderStopError("Unresolved earlier address update; intervention required.")
        if prior is None:
            try:
                response = self._json_object(self.request_text(
                base + "/api/v1/records/" + quote(record_id, safe="") + "/address",
                headers=headers, method="PUT",
                payload={"address": address, "request_id": key},
                accepted_status=(202,),
            ))
            except ProviderHTTPError:
                raise ProviderStopError("DDNS API rejected the update; intervention required.") from None
            identifier = response.get("intent_id")
        else:
            identifier = prior["intent_id"]
            response = {"intent_id": identifier, "status": "pending"}
        if (not isinstance(identifier, str) or
                not re.fullmatch(r"[a-fA-F0-9-]{36}", identifier) or
                response.get("status") not in ("pending", "applying", "applied")):
            raise ProviderStopError("DDNS API did not return a valid update intent.") from None

        if prior is None and state_store is not None:
            state_store.record_pending(state_key, address, identifier)
            state_store.save()

        for _ in range(self.max_polls):
            try:
                result = self._json_object(self.request_text(
                    base + "/api/v1/intents/" + quote(identifier, safe=""),
                    headers=headers,
                ))
            except ProviderHTTPError:
                raise ProviderStopError("Cannot verify queued DNS update; intervention required.") from None
            if result.get("intent_id") != identifier:
                raise ProviderStopError("DNS update status identifier mismatch.") from None
            state = result.get("status")
            if state == "applied":
                if state_store is not None:
                    state_store.clear_pending(state_key)
                    state_store.save()
                return True
            if state not in ("pending", "applying"):
                raise ProviderStopError("DNS update failed or status unknown; intervention required.")
        # CLI persistent stop state prevents unattended re-submission after an
        # unconfirmed result. The server intent remains available to an operator.
        raise ProviderStopError("DNS update still pending; intervention required before retry.")


class UniversalDDNSDynDNS2(DDNSProvider):
    """Experimental loopback DynDNS2 client; distinct from the safer REST adapter."""

    required_fields = ("base_url", "hostname", "token")
    requires_persistent_state = True

    @staticmethod
    def validate_settings(config):
        # Reuse the strictly loopback-only URL policy from the REST adapter.
        UniversalDDNSServer.validate_settings({
            "base_url": config.get("base_url", ""),
            "record_id": "dyndns",
            "token": config.get("token", ""),
        })
        hostname = config.get("hostname", "")
        if not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", hostname) or ".." in hostname:
            raise ProviderError("Invalid managed DynDNS2 hostname.")

    def __init__(self, name, config):
        self.validate_settings(config)
        super().__init__(name, config)

    def update_ddns(self):
        self.validate_settings(self.config)
        address = self.validate_ipv4(self.external_ip)
        base = self.config["base_url"].rstrip("/")
        try:
            text = self.request_text(
                base + "/nic/update",
                params={"hostname": self.config["hostname"], "myip": address},
                auth=("token", self.config["token"]),
            ).strip()
        except ProviderHTTPError:
            raise ProviderStopError("DynDNS2 server rejected request.") from None
        if text in ("good " + address, "nochg " + address):
            return True
        if text == "911":
            # The request may be queued and later applied; never blindly retry.
            raise ProviderStopError("DynDNS2 update unconfirmed; inspect server intent before retry.")
        raise ProviderStopError("DynDNS2 response rejected or unrecognized; intervention required.")
