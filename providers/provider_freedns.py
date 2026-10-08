"""FreeDNS.afraid.org API-v1 direct-key updates (offline validated)."""
import re
from urllib.parse import quote

from .ddns_provider import DDNSProvider, ProviderError


class FreeDNS(DDNSProvider):
    required_fields = ('api_key', 'hostname')

    def __init__(self, name, config):
        key = config.get('api_key', '')
        # Accept only the key, never a complete URL or extra query options.
        if not re.fullmatch(r'[A-Za-z0-9+/=_-]+', key):
            raise ProviderError('FreeDNS requires a direct update key.')
        super().__init__(name, config)
        self.api_key = key

    def update_ddns(self):
        ip = self.validate_ipv4(self.external_ip)
        url = 'https://freedns.afraid.org/dynamic/update.php?' + quote(self.api_key, safe='')
        body = self.request_text(url, {'address': ip}).strip()
        hostname = re.escape(self.config['hostname'])
        updated = re.fullmatch(
            rf'Updated (?:[1-9][0-9]* host\(s\) )?{hostname} to {re.escape(ip)} in [0-9]+(?:\.[0-9]+)? seconds\.?',
            body,
        )
        unchanged = body == f'ERROR: Address {ip} has not changed.'
        if not (updated or unchanged):
            raise ProviderError('FreeDNS returned an unrecognized or rejected update.')
        return True
