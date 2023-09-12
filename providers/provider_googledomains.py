from ddns_updater import DDNSProvider
import requests

class GoogleDomains(DDNSProvider):
    def __init__(self, name, config):
        super().__init__(name, config)
        self.api_key = self.config['api_key']

    def update_ddns(self):
        try:
            hostname = self.config['hostname']

            # Obtain the current external IP
            external_ip = self.external_ip

            # Google Domains update URL
            update_url = f'https://domains.google.com/nic/update'
            params = {
                'hostname': hostname,
                'myip': external_ip,
            }

            headers = {
                'Authorization': f'Basic {self.api_key}',
            }

            response = requests.get(update_url, params=params, headers=headers)
            response.raise_for_status()

            if response.text.startswith('good'):
                print(f"Google Domains DDNS update for {hostname} successful.")
            elif response.text.startswith('nochg'):
                print(f"Google Domains DDNS update for {hostname} skipped (IP address unchanged).")
            else:
                print(f"Google Domains DDNS update failed. Response: {response.text}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to update Google Domains DDNS: {str(e)}")
