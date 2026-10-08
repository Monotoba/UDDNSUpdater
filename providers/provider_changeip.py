from .ddns_provider import DDNSProvider, ProviderError
import re

class ChangeIP(DDNSProvider):
    required_fields = ('username', 'password', 'hostname')

    def __init__(self, name, config):
        super().__init__(name, config)
        self.username = self.config['username']
        self.password = self.config['password']
        self.hostname = self.config['hostname']

    def update_ddns(self):
        external_ip = self.validate_ipv4(self.external_ip)
        text = self.request_text(
            "https://nic.changeip.com/nic/update",
            params={"hostname": self.hostname, "myip": external_ip},
            auth=(self.username, self.password),
        )
        lines = text.strip().splitlines()
        # Conservative policy for the known plain-text success heading. Do not
        # search arbitrary error/HTML bodies for words such as OK or success.
        match = re.fullmatch(r"200 Successful Update(?: \(Address Used: ([0-9.]+)\))?",
                             lines[0].strip()) if lines else None
        if match is None or (match.group(1) is not None and match.group(1) != external_ip):
            raise ProviderError("ChangeIP did not return a recognized success response.")
        return True
