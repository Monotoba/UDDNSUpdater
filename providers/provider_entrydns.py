from ddns_updater import DDNSProvider
import requests

class EntryDNS(DDNSProvider):
    def update_ddns(self):
        try:
            username = self.config['username']
            password = self.config['password']
            hostname = self.config['hostname']

            # Obtain the current external IP
            external_ip = self.external_ip

            # EntryDNS update URL (replace with the actual API endpoint)
            update_url = f'https://api.entrydns.net/update?hostname={hostname}&myip={external_ip}'

            auth = (username, password)

            response = requests.get(update_url, auth=auth)
            response.raise_for_status()

            # Adjust the response parsing based on the actual API response format
            if 'success' in response.text:
                print(f"EntryDNS DDNS update for {hostname} successful.")
            else:
                print(f"EntryDNS DDNS update failed. Response: {response.text}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to update EntryDNS DDNS: {str(e)}")
