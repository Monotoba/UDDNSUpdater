"""FreeDNS.afraid.org API-v1 direct-key updates (offline validated)."""
import re
from urllib.parse import quote

from .ddns_provider import DDNSProvider, ProviderError, ProviderHTTPError, ProviderStopError


class FreeDNS(DDNSProvider):
    required_fields = ('api_key', 'hostname')
    requires_persistent_state = True

    @classmethod
    def error_scope_class(cls):
        # Both public adapter names address the same service.
        return FreeDNS

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
        try:
            body = self.request_text(url, {'address': ip}).strip()
        except ProviderHTTPError:
            raise ProviderStopError('FreeDNS HTTP rejection requires intervention.') from None
        hostname = re.escape(self.config['hostname'])
        updated = re.fullmatch(
            rf'Updated (?:[1-9][0-9]* host\(s\) )?{hostname} to {re.escape(ip)} in [0-9]+(?:\.[0-9]+)? seconds\.?',
            body,
        )
        unchanged = body == f'ERROR: Address {ip} has not changed.'
        if not (updated or unchanged):
            raise ProviderStopError('FreeDNS did not confirm the update; intervention required.')
        return True
