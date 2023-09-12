from ddns_updater import DDNSProvider
import requests

class NamecheapDDNS(DDNSProvider):
    def update_ddns(self):
        try:
            domain = self.config['domain']
            password = self.config['password']
            hostname = self.config['hostname']

            # Obtain the current external IP
            external_ip = self.external_ip

            # Namecheap DDNS update URL
            update_url = f'https://dynamicdns.park-your-domain.com/update?host={hostname}&domain={domain}&password={password}&ip={external_ip}'

            response = requests.get(update_url)
            response.raise_for_status()

            print(f"Namecheap DDNS update for {hostname}.{domain} successful.")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to update Namecheap DDNS: {str(e)}")
