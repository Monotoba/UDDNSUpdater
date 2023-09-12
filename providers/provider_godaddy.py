from ddns_updater import DDNSProvider
import requests

class GoDaddyDDNS(DDNSProvider):
    def update_ddns(self):
        try:
            api_key = self.config['api_key']
            api_secret = self.config['api_secret']
            domain = self.config['domain']

            # Obtain the current external IP
            external_ip = self.external_ip

            # GoDaddy API URL for updating DNS record
            update_url = f'https://api.godaddy.com/v1/domains/{domain}/records/A'

            headers = {
                'Authorization': f'sso-key {api_key}:{api_secret}',
                'Content-Type': 'application/json'
            }

            data = [{
                'data': external_ip,
                'ttl': 600
            }]

            response = requests.put(update_url, json=data, headers=headers)
            response.raise_for_status()

            print(f"GoDaddy DDNS update for {domain} successful.")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to update GoDaddy DDNS: {str(e)}")
