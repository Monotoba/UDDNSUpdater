from .ddns_provider import DDNSProvider, ProviderError

class DuckDNS(DDNSProvider):
    required_fields = ('subdomain', 'token')

    def update_ddns(self):
        external_ip = self.validate_ipv4(self.external_ip)
        text = self.request_text(
            "https://www.duckdns.org/update",
            params={"domains": self.config["subdomain"], "token": self.config["token"],
                    "ip": external_ip},
        )
        # No verbose parameter is sent: the documented success body is exactly OK.
        if text.strip() != "OK":
            raise ProviderError("DuckDNS did not accept the update.")
        return True
