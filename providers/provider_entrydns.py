"""EntryDNS per-record HTTPS token updates."""
from urllib.parse import quote

from .ddns_provider import DDNSProvider, ProviderError, ProviderHTTPError, ProviderStopError


class EntryDNS(DDNSProvider):
    required_fields = ('token', 'hostname')
    requires_persistent_state = True

    def __init__(self, name, config):
        # Requests normalizes dot path segments even when quote() is used.
        if config.get('token') in ('.', '..'):
            raise ProviderError('Invalid EntryDNS record token.')
        super().__init__(name, config)

    def update_ddns(self):
        ip = self.validate_ipv4(self.external_ip)
        token = quote(self.config['token'], safe='')
        try:
            body = self.request_text(
                'https://entrydns.net/records/modify/' + token,
                {'ip': ip},
            ).strip()
        except ProviderHTTPError:
            raise ProviderStopError('EntryDNS HTTP rejection requires intervention.') from None
        if body != 'OK':
            raise ProviderStopError('EntryDNS did not confirm the update; intervention required.')
        return True
