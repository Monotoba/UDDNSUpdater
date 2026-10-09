from .ddns_provider import DDNSProvider, ProviderError, ProviderHTTPError, ProviderRetryError, ProviderStopError
import platform

class NoIP(DDNSProvider):
    required_fields = ('username', 'password', 'hostname')
    requires_persistent_state = True

    def update_ddns(self):
        external_ip = self.validate_ipv4(self.external_ip)
        hosts = self.config["hostname"].split(",")
        if any(not host.strip() for host in hosts):
            raise ProviderError("Invalid No-IP hostname list.")
        user_agent = self.config.get(
            "user_agent",
            f"Monotoba UDDNSUpdater/{platform.system()}-development "
            "https://github.com/Monotoba/UDDNSUpdater/issues",
        )
        if not user_agent.strip() or any(ord(c) < 32 or ord(c) > 126 for c in user_agent):
            raise ProviderError("Invalid No-IP User-Agent.")
        try:
            text = self.request_text(
                "https://dynupdate.no-ip.com/nic/update",
                params={"hostname": self.config["hostname"], "myip": external_ip},
                auth=(self.config["username"], self.config["password"]),
                headers={"User-Agent": user_agent},
            )
        except ProviderHTTPError as error:
            if error.status == 500:
                raise ProviderRetryError(1800) from None
            raise ProviderStopError("No-IP HTTP rejection requires intervention.") from None
        lines = text.strip().splitlines()
        if any(line.strip() in {'nohost', 'badauth', 'badagent', '!donator', 'abuse'} for line in lines):
            raise ProviderStopError("No-IP requires user intervention before further updates.")
        if any(line.strip() == '911' for line in lines):
            raise ProviderRetryError(1800)
        if len(lines) != len(hosts):
            raise ProviderStopError("No-IP returned an unexpected result count; intervention required.")
        for line in lines:
            parts = line.split()
            if (len(parts) != 2 or parts[0] not in ("good", "nochg")
                    or parts[1] != external_ip):
                raise ProviderStopError("No-IP did not confirm the requested IPv4 update; intervention required.")
        return True
