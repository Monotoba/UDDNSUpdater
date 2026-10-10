import ipaddress

import requests
import sys


class ProviderError(RuntimeError):
    """Credential-safe request or response failure."""


class ProviderHTTPError(ProviderError):
    def __init__(self, status):
        super().__init__("Provider HTTP request was not accepted.")
        self.status = status


class ProviderStopError(ProviderError):
    """Provider requires intervention before another request."""


class ProviderRetryError(ProviderError):
    def __init__(self, retry_seconds):
        super().__init__("Provider requires a retry cooldown.")
        self.retry_seconds = retry_seconds


class DDNSProvider:
    # Conservative client policy, not an inferred provider retry specification.
    transport_retry_seconds = 1800
    required_fields = ()
    request_timeout = (5, 15)
    max_response_chars = 65536

    def __init__(self, name, config):
        self.name = name
        self.config = config
        for key in self.required_fields:
            if not config.get(key, "").strip():
                raise ProviderError("Missing required provider configuration.")
        self.external_ip = self.get_external_ip()

    @staticmethod
    def validate_ipv4(value):
        try:
            return str(ipaddress.IPv4Address(value))
        except (ValueError, TypeError):
            raise ProviderError("Invalid IPv4 address.") from None

    def request_text(self, url, params=None, *, auth=None, headers=None,
                     method="GET", payload=None, accepted_status=(200,)):
        response = None
        try:
            options = {"params": params, "timeout": self.request_timeout,
                       "allow_redirects": False}
            if auth is not None:
                options["auth"] = auth
            if headers is not None:
                options["headers"] = headers
            if method == "PUT":
                response = requests.put(url, json=payload, **options)
            else:
                response = requests.get(url, **options)
            if response.status_code not in accepted_status:
                raise ProviderHTTPError(response.status_code)
            text = response.text
            if len(text) > self.max_response_chars:
                raise ProviderError("Provider response exceeds parsing limit.")
            return text
        except requests.exceptions.RequestException:
            raise ProviderRetryError(self.transport_retry_seconds) from None
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    raise ProviderError("Cannot close provider response.") from None

    def get_external_ip(self):
        # ipify's IPv4-only plain-text endpoint; reject HTML and IPv6 responses.
        try:
            text = self.request_text("https://api.ipify.org").strip()
        except ProviderHTTPError:
            raise ProviderRetryError(self.transport_retry_seconds) from None
        return self.validate_ipv4(text)

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
