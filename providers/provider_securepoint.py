from ddns_updater import DDNSProvider
import requests

class SecurePoint(DDNSProvider):
    def update_ddns(self):
        try:
            username = self.config['username']
            password = self.config['password']
            hostname = self.config['hostname']

            # Obtain the current external IP
            external_ip = self.external_ip

            # SecurePoint DynDNS update URL
            update_url = f'https://www.securepoint.de/cgi-bin/noip.pl?hostname={hostname}&myip={external_ip}'

            auth = (username, password)

            response = requests.get(update_url, auth=auth)
            response.raise_for_status()

            if 'good' in response.text:
                print(f"SecurePoint DynDNS update for {hostname} successful.")
            else:
                print(f"SecurePoint DynDNS update failed. Response: {response.text}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to update SecurePoint DynDNS: {str(e)}")
