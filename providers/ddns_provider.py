import requests
import sys


class DDNSProvider:
    required_fields = ()

    def __init__(self, name, config):
        self.name = name
        self.config = config
        self.external_ip = self.get_external_ip()

    def get_external_ip(self):
        try:
            response = requests.get('https://echoip.com')
            response.raise_for_status()
            return response.text.strip()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to retrieve external IP: {str(e)}")

    def update_ddns(self):
        raise NotImplementedError("Subclasses must implement update_ddns method.")


def load_provider_classes():
    # Keep the legacy helper while using the same discovery implementation.
    from ddns_updater import load_provider_classes as discover
    return discover()


def main(argv=None):
    # Route the legacy entry point through the same validated CLI.
    from ddns_updater import main as run
    return run(argv)


if __name__ == "__main__":
    sys.exit(main())
