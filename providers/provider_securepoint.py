from .ddns_provider import DDNSProvider, ProviderError

class SecurePoint(DDNSProvider):
    required_fields = ('username', 'password', 'hostname')

    def update_ddns(self):
        external_ip = self.validate_ipv4(self.external_ip)
        text = self.request_text(
            "https://update.spdyn.de/nic/update",
            params={"hostname": self.config["hostname"], "myip": external_ip},
            auth=(self.config["username"], self.config["password"]),
        )
        parts = text.strip().split()
        if (len(parts) not in (1, 2) or parts[0] not in ("good", "nochg")
                or (len(parts) == 2 and parts[1] != external_ip)):
            raise ProviderError("Securepoint did not return a recognized acceptance response.")
        return True
