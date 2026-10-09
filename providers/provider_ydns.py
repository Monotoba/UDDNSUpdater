from .ddns_provider import DDNSProvider, ProviderError, ProviderHTTPError, ProviderStopError


class YDNS(DDNSProvider):
    required_fields = ("hostname", "username", "password")
    requires_persistent_state = True

    @staticmethod
    def normalize_settings(config):
        settings = dict(config)
        # Retain old keys when they can actually represent API-v1 inputs.
        for old, new in (("domain_id", "hostname"), ("api_key", "password"),
                         ("api_username", "username")):
            if new not in settings and old in settings:
                settings[new] = settings[old]
        return settings

    def __init__(self, name, config):
        settings = self.normalize_settings(config)
        if settings.get("hostname", "").strip().isdigit():
            raise ProviderError("YDNS needs a hostname, not a numeric domain ID.")
        super().__init__(name, settings)
        # Preserve the legacy attributes while using the documented API inputs.
        self.domain_id = self.config["hostname"]
        self.api_key = self.config["password"]

    def update_ddns(self):
        external_ip = self.validate_ipv4(self.external_ip)
        try:
            text = self.request_text(
                "https://ydns.io/api/v1/update/",
                params={"host": self.config["hostname"], "ip": external_ip},
                auth=(self.config["username"], self.config["password"]),
            )
        except ProviderHTTPError:
            raise ProviderStopError("YDNS HTTP rejection requires intervention.") from None
        if text.strip() != "good":
            raise ProviderStopError("YDNS did not confirm the update; intervention required.")
        return True
