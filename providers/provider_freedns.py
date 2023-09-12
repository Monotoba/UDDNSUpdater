from ddns_updater import DDNSProvider
import requests

class FreeDNS(DDNSProvider):
    def __init__(self, name, config):
        super().__init__(name, config)
        self.api_key = self.config['api_key']

    def update_ddns(self):
        try:
            hostname = self.config['hostname']

            # Obtain the current external IP
            external_ip = self.external_ip

            # FreeDNS update URL
            update_url = f'https://freedns.afraid.org/dynamic/update.php'
            params = {
                'hostname': hostname,
                'myip': external_ip,
                'action': 'update',
            }

            headers = {
                'Authorization': f'Bearer {self.api_key}',
            }

            response = requests.get(update_url, params=params, headers=headers)
            response.raise_for_status()

            if 'Updated' in response.text:
                print(f"FreeDNS DDNS update for {hostname} successful.")
            else:
                print(f"FreeDNS DDNS update failed. Response: {response.text}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to update FreeDNS DDNS: {str(e)}")
