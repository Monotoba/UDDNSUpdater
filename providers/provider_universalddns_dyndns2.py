"""Experimental DynDNS2 loopback adapter for UniversalDDNSServer."""
import re
from .ddns_provider import DDNSProvider, ProviderError, ProviderHTTPError, ProviderStopError
from .provider_universalddns import UniversalDDNSServer


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
