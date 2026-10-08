"""ClouDNS per-record IPv4 DynamicURL updates."""
from .ddns_provider import DDNSProvider, ProviderError


class CloudNS(DDNSProvider):
    required_fields = ('api_key', 'hostname')

    def __init__(self, name, config):
        super().__init__(name, config)
        self.api_key = self.config['api_key']
        self.hostname = self.config['hostname']

    def update_ddns(self):
        ip = self.validate_ipv4(self.external_ip)
        body = self.request_text(
            'https://ipv4.cloudns.net/api/dynamicURL/',
            {'q': self.api_key, 'ip': ip},
        ).strip()
        if body != 'OK':
            raise ProviderError('ClouDNS returned an unrecognized or rejected update.')
        return True
