from ddns_updater import DDNSProvider
import requests

class DuckDNS(DDNSProvider):
    def update_ddns(self):
        try:
            subdomain = self.config['subdomain']
            token = self.config['token']

            # Obtain the current external IP
            external_ip = self.external_ip

            # DuckDNS update URL
            update_url = f'https://www.duckdns.org/update?domains={subdomain}&token={token}&ip={external_ip}'

            response = requests.get(update_url)
            response.raise_for_status()

            print(f"DuckDNS update for {subdomain}.duckdns.org successful.")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to update DuckDNS: {str(e)}")
