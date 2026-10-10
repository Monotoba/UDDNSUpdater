from urllib.parse import quote
import json
import re

from .ddns_provider import DDNSProvider, ProviderError, ProviderHTTPError, ProviderStopError


class GoDaddyDDNS(DDNSProvider):
    required_fields = ("api_key", "api_secret", "domain", "hostname")
    requires_persistent_state = True

    @classmethod
    def required_fields_for(cls, config):
        if config.get('api_version', 'v1') == 'v3':
            return ('pat', 'domain', 'hostname', 'record_id')
        return cls.required_fields

    @staticmethod
    def validate_settings(config):
        version = config.get('api_version', 'v1')
        if version not in ('v1', 'v3'):
            raise ProviderError('Unsupported GoDaddy API version.')
        if version == 'v3':
            if not re.fullmatch(r'[!-~]+', config.get('pat', '')):
                raise ProviderError('Invalid GoDaddy PAT.')
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,256}', config.get('record_id', '')):
                raise ProviderError('Invalid GoDaddy record identifier.')
            domain = config.get('domain', '')
            if (len(domain) > 253 or not re.fullmatch(r'[A-Za-z0-9.-]+', domain)
                    or any(not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label)
                           for label in domain.split('.'))):
                raise ProviderError('GoDaddy v3 requires a punycode zone name.')
            hostname = config.get('hostname', '')
            if not re.fullmatch(r'[A-Za-z0-9_.*@-]{1,255}', hostname) or hostname in ('.', '..'):
                raise ProviderError('Invalid GoDaddy record name.')
            ttl = config.get('ttl', '600')
            if not re.fullmatch(r'[0-9]{3,5}', ttl) or not 600 <= int(ttl) <= 86400:
                raise ProviderError('Invalid GoDaddy record TTL.')

    def __init__(self, name, config):
        self.validate_settings(config)
        super().__init__(name, config)

    def update_v3(self, external_ip):
        payload = {'name': self.config['hostname'], 'type': 'A', 'data': external_ip,
                   'ttl': int(self.config.get('ttl', '600'))}
        try:
            text = self.request_text(
                'https://api.godaddy.com/v3/domains/zones/'+quote(self.config['domain'], safe='')+
                '/dns-records/'+quote(self.config['record_id'], safe=''),
                headers={'Authorization': 'Bearer '+self.config['pat'], 'Content-Type': 'application/json'},
                method='PUT', payload=payload,
            )
        except ProviderHTTPError:
            raise ProviderStopError('GoDaddy HTTP rejection requires intervention.') from None
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError
                result[key] = value
            return result
        try:
            response = json.loads(text, object_pairs_hook=unique)
            if (not isinstance(response, dict) or response.get('recordId') != self.config['record_id']
                    or any(response.get(key) != value for key, value in payload.items())
                    or type(response.get('ttl')) is not int):
                raise ValueError
        except (ValueError, TypeError, RecursionError):
            raise ProviderStopError('GoDaddy did not confirm the v3 record update; intervention required.') from None
        return True

    def update_ddns(self):
        external_ip = self.validate_ipv4(self.external_ip)
        if self.config.get('api_version', 'v1') == 'v3':
            return self.update_v3(external_ip)
        # Always scope replacement to an explicit A-record name, never all A records.
        domain = quote(self.config["domain"], safe="")
        name = quote(self.config["hostname"], safe="")
        if self.config["domain"] in (".", "..") or self.config["hostname"] in (".", ".."):
            raise ProviderError("Invalid GoDaddy record target.")
        authorization = f"sso-key {self.config['api_key']}:{self.config['api_secret']}"
        if any(ord(c) < 32 or ord(c) > 126 for c in authorization):
            raise ProviderError("Invalid GoDaddy authorization configuration.")
        try:
            text = self.request_text(
                f"https://api.godaddy.com/v1/domains/{domain}/records/A/{name}",
                headers={"Authorization": authorization, "Content-Type": "application/json"},
                method="PUT", payload=[{"data": external_ip, "ttl": 600}],
                accepted_status=(200, 204),
            )
        except ProviderHTTPError:
            raise ProviderStopError("GoDaddy HTTP rejection requires intervention.") from None
        # The reference's response table lists 200; its prose lists 204. Both
        # represent no-content acceptance. An unexpected body is not success.
        if text.strip():
            raise ProviderStopError("GoDaddy did not confirm the update; intervention required.")
        return True
