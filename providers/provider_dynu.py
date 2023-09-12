from ddns_updater import DDNSProvider
import requests

class Dynu(DDNSProvider):
    def update_ddns(self):
        try:
            username = self.config['username']
            password = self.config['password']
            hostname = self.config['hostname']

            # Obtain the current external IP
            external_ip = self.external_ip

            # Dynu update URL
            update_url = f'https://api.dynu.com/nic/update'
            params = {
                'hostname': hostname,
                'myip': external_ip,
                'username': username,
                'password': password,
            }

            response = requests.get(update_url, params=params)
            response.raise_for_status()

            if response.text.startswith('good'):
                print(f"Dynu DDNS update for {hostname} successful.")
            elif response.text.startswith('nochg'):
                print(f"Dynu DDNS update for {hostname} skipped (IP address unchanged).")
            else:
                print(f"Dynu DDNS update failed. Response: {response.text}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to update Dynu DDNS: {str(e)}")
