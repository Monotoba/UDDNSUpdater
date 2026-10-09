from .ddns_provider import DDNSProvider, ProviderHTTPError, ProviderStopError

class SecurePoint(DDNSProvider):
    required_fields = ('username', 'password', 'hostname')
    requires_persistent_state = True

    @classmethod
    def error_scope_class(cls):
        # Both public class names address the same service.
        return SecurePoint

    def update_ddns(self):
        external_ip = self.validate_ipv4(self.external_ip)
        try:
            text = self.request_text(
                "https://update.spdyn.de/nic/update",
                params={"hostname": self.config["hostname"], "myip": external_ip},
                auth=(self.config["username"], self.config["password"]),
            )
        except ProviderHTTPError:
            raise ProviderStopError("Securepoint HTTP rejection requires intervention.") from None
        parts = text.strip().split()
        if (len(parts) not in (1, 2) or parts[0] not in ("good", "nochg")
                or (len(parts) == 2 and parts[1] != external_ip)):
            raise ProviderStopError("Securepoint did not confirm the update; intervention required.")
        return True
