from ddns_updater import DDNSProvider
import requests

class SpDYN(DDNSProvider):
    def update_ddns(self):
        try:
            username = self.config['username']
            password = self.config['password']
            hostname = self.config['hostname']

            # Obtain the current external IP
            external_ip = self.external_ip

            # spDYN update URL (replace with the actual API endpoint)
            update_url = f'https://api.spdyn.de/update?hostname={hostname}&ip={external_ip}'

            auth = (username, password)

            response = requests.get(update_url, auth=auth)
            response.raise_for_status()

            # Adjust the response parsing based on the actual API response format
            if 'success' in response.text:
                print(f"spDYN DDNS update for {hostname} successful.")
            else:
                print(f"spDYN DDNS update failed. Response: {response.text}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to update spDYN DDNS: {str(e)}")
