"""ClouDNS per-record IPv4 DynamicURL updates."""
from .ddns_provider import DDNSProvider, ProviderHTTPError, ProviderStopError


class CloudNS(DDNSProvider):
    required_fields = ('api_key', 'hostname')
    requires_persistent_state = True

    def __init__(self, name, config):
        super().__init__(name, config)
        self.api_key = self.config['api_key']
        self.hostname = self.config['hostname']

    def update_ddns(self):
        ip = self.validate_ipv4(self.external_ip)
        try:
            body = self.request_text(
                'https://ipv4.cloudns.net/api/dynamicURL/',
                {'q': self.api_key, 'ip': ip},
            ).strip()
        except ProviderHTTPError:
            raise ProviderStopError('ClouDNS HTTP rejection requires intervention.') from None
        if body != 'OK':
            raise ProviderStopError('ClouDNS did not confirm the update; intervention required.')
        return True
