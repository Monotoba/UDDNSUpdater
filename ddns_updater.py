import argparse
import configparser
import logging
import os
import platform
import sys

from providers.ddns_provider import DDNSProvider


def load_provider_classes():
    provider_classes = {}
    provider_dir = 'providers'

    # Dynamically import all provider classes from the providers directory
    for filename in os.listdir(provider_dir):
        if filename.startswith("provider_") and filename.endswith(".py"):
            module_name = filename[:-3]  # Remove .py extension
            module = __import__(f"{provider_dir}.{module_name}", fromlist=["Provider"])
            for name, cls in vars(module).items():
                if isinstance(cls, type) and issubclass(cls, DDNSProvider) and cls is not DDNSProvider:
                    provider_classes[name] = cls

    return provider_classes


def main():
    parser = argparse.ArgumentParser(description="DDNS Updater")
    parser.add_argument("--no-log", action="store_true", help="Disable logging")
    args = parser.parse_args()

    try:
        config = configparser.ConfigParser()
        config.read('config.ini')

        # Determine the current operating system
        current_os = platform.system()

        # Initialize logging if not disabled
        if not args.no_log:
            logging.basicConfig(filename='ddns_update.log', level=logging.ERROR)

        provider_classes = load_provider_classes()

        for section in config.sections():
            service_name = section
            service_settings = config[section]

            provider_name = service_settings['ddns_provider']
            if provider_name not in provider_classes:
                print(f"Unsupported DDNS provider: {provider_name}", file=sys.stderr)
                continue

            provider_class = provider_classes[provider_name]
            provider = provider_class(service_name, service_settings)

            try:
                provider.update_ddns()
            except Exception as e:
                error_message = f"Error updating {service_name}: {str(e)}"
                if not args.no_log:
                    logging.error(error_message)
                print(error_message, file=sys.stderr)

        # Close the log file if logging is enabled
        if not args.no_log:
            logging.shutdown()
    except Exception as e:
        print(f"An error occurred: {str(e)}", file=sys.stderr)


if __name__ == "__main__":
    main()
