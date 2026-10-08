from .ddns_provider import DDNSProvider, ProviderError


class GoogleDomains(DDNSProvider):
    required_fields = ("api_key", "hostname")
    disabled_reason = "Google Domains DDNS is unavailable; select another provider."

    def __init__(self, name, config):
        # Preserve the discoverable class but never contact the retired service.
        raise ProviderError(self.disabled_reason)

    def update_ddns(self):
        raise ProviderError(self.disabled_reason)
