"""Retain the legacy class name for a service that has closed."""
from .ddns_provider import DDNSProvider, ProviderError


class DNSMax(DDNSProvider):
    required_fields = ('username', 'password', 'hostname')
    disabled_reason = 'DNSMax is unavailable; the service closed. Select another provider.'

    def __init__(self, name, config):
        raise ProviderError(self.disabled_reason)

    def update_ddns(self):
        raise ProviderError(self.disabled_reason)
