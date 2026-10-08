from urllib.parse import quote

from .ddns_provider import DDNSProvider, ProviderError


class GoDaddyDDNS(DDNSProvider):
    required_fields = ("api_key", "api_secret", "domain", "hostname")

    def update_ddns(self):
        external_ip = self.validate_ipv4(self.external_ip)
        # Always scope replacement to an explicit A-record name, never all A records.
        domain = quote(self.config["domain"], safe="")
        name = quote(self.config["hostname"], safe="")
        if self.config["domain"] in (".", "..") or self.config["hostname"] in (".", ".."):
            raise ProviderError("Invalid GoDaddy record target.")
        authorization = f"sso-key {self.config['api_key']}:{self.config['api_secret']}"
        if any(ord(c) < 32 or ord(c) > 126 for c in authorization):
            raise ProviderError("Invalid GoDaddy authorization configuration.")
        text = self.request_text(
            f"https://api.godaddy.com/v1/domains/{domain}/records/A/{name}",
            headers={"Authorization": authorization, "Content-Type": "application/json"},
            method="PUT", payload=[{"data": external_ip, "ttl": 600}],
            accepted_status=(200, 204),
        )
        # The reference's response table lists 200; its prose lists 204. Both
        # represent no-content acceptance. An unexpected body is not success.
        if text.strip():
            raise ProviderError("GoDaddy returned an unexpected response body.")
        return True
