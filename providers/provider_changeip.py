from .ddns_provider import DDNSProvider, ProviderError, ProviderHTTPError, ProviderStopError
import re

class ChangeIP(DDNSProvider):
    required_fields = ('username', 'password', 'hostname')
    requires_persistent_state = True

    @staticmethod
    def validate_settings(config):
        hostname = config.get('hostname', '')
        if not isinstance(hostname, str):
            raise ProviderError('Invalid ChangeIP hostname.')
        for target in hostname.split(','):
            target = target.strip().rstrip('.').casefold()
            if target == 'changeip.com' or target.endswith('.changeip.com'):
                raise ProviderError('ChangeIP discontinued changeip.com DDNS domains.')

    def __init__(self, name, config):
        self.validate_settings(config)
        super().__init__(name, config)
        self.username = self.config['username']
        self.password = self.config['password']
        self.hostname = self.config['hostname']

    def update_ddns(self):
        external_ip = self.validate_ipv4(self.external_ip)
        try:
            text = self.request_text(
                "https://nic.changeip.com/nic/update",
                params={"hostname": self.hostname, "myip": external_ip},
                auth=(self.username, self.password),
            )
        except ProviderHTTPError:
            raise ProviderStopError("ChangeIP HTTP rejection requires intervention.") from None
        lines = text.strip().splitlines()
        # Conservative policy for the known plain-text success heading. Do not
        # search arbitrary error/HTML bodies for words such as OK or success.
        match = re.fullmatch(r"200 Successful Update(?: \(Address Used: ([0-9.]+)\))?",
                             lines[0].strip()) if lines else None
        if match is None or (match.group(1) is not None and match.group(1) != external_ip):
            raise ProviderStopError("ChangeIP did not confirm the update; intervention required.")
        return True
