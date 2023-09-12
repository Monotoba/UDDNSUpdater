from ddns_updater import DDNSProvider
import requests

class NoIP(DDNSProvider):
    def update_ddns(self):
        try:
            username = self.config['username']
            password = self.config['password']
            hostname = self.config['hostname']

            # Obtain the current external IP
            external_ip = self.external_ip

            # No-IP update URL
            update_url = f'https://dynupdate.no-ip.com/nic/update?hostname={hostname}'
            auth = (username, password)

            response = requests.get(update_url, auth=auth, params={'myip': external_ip})
            response.raise_for_status()

            if 'good' in response.text:
                print(f"No-IP DDNS update for {hostname} successful.")
            else:
                print(f"No-IP DDNS update failed. Response: {response.text}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to update No-IP DDNS: {str(e)}")
