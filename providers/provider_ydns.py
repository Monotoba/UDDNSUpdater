from ddns_updater import DDNSProvider
import requests

class YDNS(DDNSProvider):
    def __init__(self, name, config):
        super().__init__(name, config)
        self.domain_id = self.config['domain_id']
        self.api_key = self.config['api_key']

    def update_ddns(self):
        try:
            # Obtain the current external IP
            external_ip = self.external_ip

            # YDNS update URL
            update_url = f'https://ydns.io/api/v1/update'
            params = {
                'domain': self.domain_id,
                'ip': external_ip,
                'apikey': self.api_key,
            }

            response = requests.get(update_url, params=params)
            response.raise_for_status()

            if 'good' in response.text:
                print(f"YDNS DDNS update for {self.domain_id} successful.")
            else:
                print(f"YDNS DDNS update failed. Response: {response.text}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to update YDNS DDNS: {str(e)}")
