# CLI configuration and status codes

UDDNSUpdater is a work-in-progress prototype. Use Python 3.10+ with dependencies
from `requirements.txt`. Start with `python ddns_updater.py --help`.

## Configuration-only evaluation

Create a UTF-8 INI file. Each section represents one service and selects an exact
provider class name. For an offline Namecheap example:

```ini
[evaluation]
ddns_provider = NamecheapDDNS
domain = example.net
hostname = @
password = evaluation-only-password
```

Run from the checkout, substituting your file path:

```sh
python ddns_updater.py --config-file /path/to/settings.ini --dry-run
```

This checks required values and provider selection without constructing providers,
discovering an IP, contacting services, writing logs, or scheduling tasks. It does
not verify credentials, domain/hostname validity, current provider API support,
or DNS propagation. Example values above are only for dry-run evaluation.

Every service is validated before any real request is attempted. The file must
exist, parse as INI, and contain at least one service section. Duplicate sections
or keys, blank required values, and values starting with `YOUR_` (case-insensitive)
are rejected. INI interpolation is disabled, so `%` characters in credentials
remain literal. Standard INI whitespace stripping and inherited DEFAULT values
still apply. Unrecognized extra keys are retained but may be ignored by adapters.
Do not mix scheduler sections into this file; scheduling is a separate component.

## Required adapter settings

These reflect what the existing adapter code reads, not verified service contracts.
Every row also requires `ddns_provider` set to the indicated class name.

| Class names | Required settings |
| --- | --- |
| Afraid, ChangeIP, CloudNS, DNSMax, Dynu, EntryDNS, EuroDynDNS, NoIP, SecurePoint, SpDYN | username, password, hostname |
| DuckDNS | subdomain, token |
| FreeDNS, GoogleDomains | api_key, hostname |
| GoDaddyDDNS | api_key, api_secret, domain |
| NamecheapDDNS | domain, password, hostname |
| YDNS | domain_id, api_key |

Protect configuration files using your OS file permissions and keep them out of
version control. Credentials are currently read from INI; environment-variable
credential loading is not implemented.

## Real-run behavior and logging

Without `--dry-run`, providers are constructed and run in section order. Adapter
construction can itself discover the public IP. A raised exception produces a
controlled error identifying only the service number, and later services are
still attempted. This is not a transaction: earlier DNS changes are not rolled back.

The default configuration is `config.ini` in the working directory. By default,
errors go to `ddns_update.log` there; `--no-log` disables file logging. Configuration
errors and dry runs do not open the log. A log-open failure blocks all updates.
Log handles close after each CLI invocation. Raw exception strings, section names,
adapter prints, and provider bodies are withheld by the CLI. The repaired
Namecheap/DuckDNS/No-IP/Dynu adapters also emit controlled exceptions on direct calls.
Other direct adapter calls bypass this protection and should not use real credentials.

| Exit code | Meaning |
| --- | --- |
| 0 | Valid dry run, or every real-run adapter returned without raising |
| 1 | Adapter-loading, runtime, or logging failure |
| 2 | Invalid/unreadable configuration or command-line arguments |

Namecheap/DuckDNS/No-IP/Dynu now return explicit acceptance only after their response checks
pass, and rejected/malformed responses produce code 1. Acceptance does not verify
DNS propagation. The other 12 legacy adapters can print rejection and return
normally, so code 0 does **not** confirm success for those services. Their request
contracts are still pending review. A failure exit also does not prove DNS stayed
unchanged. See [provider repair status](PROVIDERS.md).

Use `python -m ddns_updater` for the same CLI. The legacy
`providers.ddns_provider.main()` function delegates to this validated entry point.
Native scheduler behavior is still incomplete; no release is available.
