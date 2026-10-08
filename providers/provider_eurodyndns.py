"""EuroDynDNS HTTPS updates with conservative status parsing."""
import re

from .ddns_provider import DDNSProvider, ProviderError


class EuroDynDNS(DDNSProvider):
    required_fields = ('username', 'password', 'hostname')

    def __init__(self, name, config):
        super().__init__(name, config)
        self.username = self.config['username']
        self.password = self.config['password']
        self.hostname = self.config['hostname']

    def update_ddns(self):
        ip = self.validate_ipv4(self.external_ip)
        body = self.request_text(
            'https://update.eurodyndns.org/update/',
            {'hostname': self.hostname, 'myip': ip},
            auth=(self.username, self.password),
        ).strip()
        if not re.fullmatch(rf'(?:good|nochg)(?:[ \t]+{re.escape(ip)})?', body):
            raise ProviderError('EuroDynDNS did not accept the requested IPv4 update.')
        return True
