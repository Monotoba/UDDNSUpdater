from ddns_updater import DDNSProvider
import requests

class DNSMax(DDNSProvider):
    def __init__(self, name, config):
        super().__init__(name, config)
        self.username = self.config['username']
        self.password = self.config['password']
        self.hostname = self.config['hostname']

    def update_ddns(self):
        try:
            # Obtain the current external IP
            external_ip = self.external_ip

            # DNS MAX update URL (replace with the actual API endpoint)
            update_url = 'https://api.dnsmas.net/ddns/update'
            params = {
                'hostname': self.hostname,
                'myip': external_ip,
            }

            auth = (self.username, self.password)

            response = requests.get(update_url, params=params, auth=auth)
            response.raise_for_status()

            # Adjust the response parsing based on the actual API response format
            if 'success' in response.text:
                print(f"DNS MAX DDNS update for {self.hostname} successful.")
            else:
                print(f"DNS MAX DDNS update failed. Response: {response.text}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to update DNS MAX DDNS: {str(e)}")
