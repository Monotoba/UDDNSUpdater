from .ddns_provider import DDNSProvider, ProviderHTTPError, ProviderStopError

class DuckDNS(DDNSProvider):
    required_fields = ('subdomain', 'token')
    requires_persistent_state = True

    def update_ddns(self):
        external_ip = self.validate_ipv4(self.external_ip)
        try:
            text = self.request_text(
                "https://www.duckdns.org/update",
                params={"domains": self.config["subdomain"], "token": self.config["token"],
                        "ip": external_ip},
            )
        except ProviderHTTPError:
            raise ProviderStopError("DuckDNS HTTP rejection requires intervention.") from None
        # No verbose parameter is sent: the documented success body is exactly OK.
        if text.strip() != "OK":
            raise ProviderStopError("DuckDNS did not confirm the update; intervention required.")
        return True
