from ddns_updater import DDNSProvider
import requests

class EuroDynDNS(DDNSProvider):
    def __init__(self, name, config):
        super().__init__(name, config)
        self.username = self.config['username']
        self.password = self.config['password']
        self.hostname = self.config['hostname']

    def update_ddns(self):
        try:
            # Obtain the current external IP
            external_ip = self.external_ip

            # EuroDynDNS update URL (replace with the actual API endpoint)
            update_url = 'https://api.eurodyndns.org/nic/update'
            params = {
                'hostname': self.hostname,
                'myip': external_ip,
            }

            auth = (self.username, self.password)

            response = requests.get(update_url, params=params, auth=auth)
            response.raise_for_status()

            if 'good' in response.text:
                print(f"EuroDynDNS DDNS update for {self.hostname} successful.")
            elif 'nochg' in response.text:
                print(f"EuroDynDNS DDNS update for {self.hostname} skipped (IP address unchanged).")
            else:
                print(f"EuroDynDNS DDNS update failed. Response: {response.text}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to update EuroDynDNS DDNS: {str(e)}")
