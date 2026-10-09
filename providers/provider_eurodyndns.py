"""EuroDynDNS HTTPS updates with conservative status parsing."""
import re

from .ddns_provider import DDNSProvider, ProviderHTTPError, ProviderStopError


class EuroDynDNS(DDNSProvider):
    required_fields = ('username', 'password', 'hostname')
    requires_persistent_state = True

    def __init__(self, name, config):
        super().__init__(name, config)
        self.username = self.config['username']
        self.password = self.config['password']
        self.hostname = self.config['hostname']

    def update_ddns(self):
        ip = self.validate_ipv4(self.external_ip)
        try:
            body = self.request_text(
                'https://update.eurodyndns.org/update/',
                {'hostname': self.hostname, 'myip': ip},
                auth=(self.username, self.password),
            ).strip()
        except ProviderHTTPError:
            raise ProviderStopError('EuroDynDNS HTTP rejection requires intervention.') from None
        if not re.fullmatch(rf'(?:good|nochg)(?:[ \t]+{re.escape(ip)})?', body):
            raise ProviderStopError('EuroDynDNS did not confirm the update; intervention required.')
        return True
