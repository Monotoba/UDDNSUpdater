import re

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

    @staticmethod
    def validate_settings(config):
        if 'record_id' in config:
            value = config['record_id']
            # Bound parsing input locally; this is not a claimed provider limit.
            if (not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,20}', value)
                    or int(value) == 0):
                raise ProviderError('YDNS record_id must be a positive decimal identifier.')

    def __init__(self, name, config):
        settings = self.normalize_settings(config)
        self.validate_settings(settings)
        if settings.get("hostname", "").strip().isdigit():
            raise ProviderError("YDNS needs a hostname, not a numeric domain ID.")
        super().__init__(name, settings)
        # Preserve the legacy attributes while using the documented API inputs.
        self.domain_id = self.config["hostname"]
        self.api_key = self.config["password"]

    def update_ddns(self):
        external_ip = self.validate_ipv4(self.external_ip)
        params = {"host": self.config["hostname"], "ip": external_ip}
        if 'record_id' in self.config:
            params['record_id'] = self.config['record_id']
        try:
            text = self.request_text(
                "https://ydns.io/api/v1/update/",
                params=params,
                auth=(self.config["username"], self.config["password"]),
            )
        except ProviderHTTPError:
            raise ProviderStopError("YDNS HTTP rejection requires intervention.") from None
        if text.strip() != "good":
            raise ProviderStopError("YDNS did not confirm the update; intervention required.")
        return True
