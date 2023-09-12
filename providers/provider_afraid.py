from ddns_updater import DDNSProvider
import requests

class Afraid(DDNSProvider):
    def update_ddns(self):
        try:
            username = self.config['username']
            password = self.config['password']
            hostname = self.config['hostname']

            # Obtain the current external IP
            external_ip = self.external_ip

            # Afraid.org update URL
            update_url = f'https://freedns.afraid.org/dynamic/update.php'
            params = {
                'hostname': hostname,
                'myip': external_ip,
            }

            auth = (username, password)

            response = requests.get(update_url, params=params, auth=auth)
            response.raise_for_status()

            if response.text.strip() == 'Updated':
                print(f"Afraid.org DDNS update for {hostname} successful.")
            else:
                print(f"Afraid.org DDNS update failed. Response: {response.text}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to update Afraid.org DDNS: {str(e)}")
