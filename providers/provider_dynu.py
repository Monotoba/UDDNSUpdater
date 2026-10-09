from .ddns_provider import DDNSProvider, ProviderHTTPError, ProviderRetryError, ProviderStopError

class Dynu(DDNSProvider):
    required_fields = ('username', 'password', 'hostname')
    requires_persistent_state = True

    def update_ddns(self):
        external_ip = self.validate_ipv4(self.external_ip)
        try:
            text = self.request_text(
                "https://api.dynu.com/nic/update",
                params={"hostname": self.config["hostname"], "myip": external_ip,
                        "myipv6": "no"},
                auth=(self.config["username"], self.config["password"]),
            )
        except ProviderHTTPError:
            # HTTP status retry timing is not specified by Dynu's protocol page;
            # require intervention rather than guessing or ignoring Retry-After.
            raise ProviderStopError("Dynu HTTP rejection requires intervention.") from None
        parts = text.strip().split()
        if parts and parts[0] in {'911', 'servererror', 'dnserr'}:
            # Dynu specifies 600 seconds for 911. Apply that same conservative
            # client delay to the retryable codes with no documented interval.
            raise ProviderRetryError(600)
        if (len(parts) not in (1, 2) or parts[0] not in ("good", "nochg")
                or (len(parts) == 2 and parts[1] != external_ip)):
            raise ProviderStopError("Dynu did not accept the requested IPv4 update; intervention required.")
        return True
