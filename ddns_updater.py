import argparse
import configparser
import logging
import importlib
from pathlib import Path
import contextlib
import io
import sys

from providers.ddns_provider import DDNSProvider


def load_provider_classes():
    provider_classes = {}
    provider_dir = Path(__file__).resolve().parent / "providers"

    # Resolve bundled modules relative to this file, independently of cwd.
    for path in sorted(provider_dir.glob("provider_*.py")):
        module = importlib.import_module(f"providers.{path.stem}")
        for name, cls in vars(module).items():
            if (isinstance(cls, type) and issubclass(cls, DDNSProvider)
                    and cls is not DDNSProvider and cls.__module__ == module.__name__):
                provider_classes[name] = cls

    return provider_classes


class ConfigurationError(ValueError):
    """A configuration problem with a credential-safe public message."""


def load_services(config_path, provider_classes):
    config = configparser.ConfigParser(interpolation=None)
    try:
        with open(config_path, encoding="utf-8") as handle:
            config.read_file(handle)
    except (OSError, UnicodeError, configparser.Error):
        raise ConfigurationError("Cannot read a valid UTF-8 configuration file.") from None
    if not config.sections():
        raise ConfigurationError("Configuration must contain at least one service section.")

    services = []
    for index, section in enumerate(config.sections(), 1):
        settings = dict(config[section])
        provider_class = provider_classes.get(settings.get("ddns_provider", "").strip())
        if provider_class is None:
            raise ConfigurationError(f"Service {index}: missing or unsupported ddns_provider.")
        normalize = getattr(provider_class, "normalize_settings", None)
        if normalize is not None:
            settings = normalize(settings)
        if provider_class.__name__ == "YDNS" and settings.get("hostname", "").strip().isdigit():
            raise ConfigurationError(f"Service {index}: YDNS requires a hostname, not a numeric domain ID.")
        for key in provider_class.required_fields:
            value = settings.get(key, "")
            if not value.strip() or value.strip().upper().startswith("YOUR_"):
                raise ConfigurationError(f"Service {index}: missing or placeholder {key}.")
        services.append((section, provider_class, settings))
    return services


def main(argv=None):
    parser = argparse.ArgumentParser(description="DDNS Updater")
    parser.add_argument("--no-log", action="store_true", help="Disable file logging")
    parser.add_argument("--config-file", default="config.ini", help="Configuration file (default: config.ini)")
    parser.add_argument("--dry-run", action="store_true", help="Validate configuration only; no network or file writes")
    args = parser.parse_args(argv)

    try:
        provider_classes = load_provider_classes()
    except Exception:
        print("Cannot load provider adapters.", file=sys.stderr)
        return 1
    try:
        services = load_services(args.config_file, provider_classes)
    except ConfigurationError as error:
        print(str(error), file=sys.stderr)
        return 2

    if args.dry_run:
        print(f"Configuration valid for {len(services)} service(s). No requests sent.")
        return 0

    # A dedicated handler avoids changing the caller's root logger or retaining
    # handles between invocations. Open it before any DNS-related request.
    handler = None
    if not args.no_log:
        try:
            handler = logging.FileHandler("ddns_update.log", encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        except Exception:
            print("Cannot open error log; no updates attempted.", file=sys.stderr)
            return 1

    failed = False
    try:
        for index, (section, provider_class, settings) in enumerate(services, 1):
            try:
                # Legacy adapters print raw provider bodies and exception URLs.
                # Suppress these until provider contracts are repaired; emit only
                # controlled CLI messages, including constructor failures.
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    provider = provider_class(section, settings)
                    result = provider.update_ddns()
                if result is True:
                    print(f"Service {index}: provider accepted the update; DNS propagation is unverified.")
                else:
                    print(f"Service {index}: adapter completed; provider success is not yet verified.")
            except Exception:
                failed = True
                message = f"Service {index}: update failed; provider details withheld."
                print(message, file=sys.stderr)
                if handler is not None:
                    try:
                        record = logging.LogRecord("UDDNSUpdater", logging.ERROR, "", 0, message, (), None)
                        handler.stream.write(handler.format(record) + "\n")
                        handler.flush()
                    except Exception:
                        print("Cannot write error log.", file=sys.stderr)
    finally:
        if handler is not None:
            try:
                handler.close()
            except Exception:
                failed = True
                print("Cannot close error log.", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
