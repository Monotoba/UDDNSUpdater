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
| ChangeIP, Dynu, EuroDynDNS, NoIP, SecurePoint, SpDYN | username, password, hostname |
| DuckDNS | subdomain, token |
| EntryDNS | token, hostname |
| Afraid, FreeDNS, CloudNS | api_key, hostname |
| GoogleDomains, DNSMax | Unavailable; retained for clear migration errors |
| GoDaddyDDNS (default v1) | api_key, api_secret, domain, hostname |
| GoDaddyDDNS (api_version=v3) | pat, domain, hostname, record_id |
| NamecheapDDNS | domain, password, hostname |
| YDNS | hostname, username, password |

Protect configuration files using your OS file permissions and keep them out of
version control. Credentials are currently read from INI; environment-variable
credential loading is not implemented.

## Real-run behavior and logging

Without `--dry-run`, providers are constructed and run in section order. Adapter
construction can itself discover the public IP. A raised exception produces a
controlled error identifying only the service number. Persistent stop/cooldown
errors abort remaining services; ordinary runtime failures continue to later services. This is not a transaction: earlier DNS changes are not rolled back.

The default configuration is `config.ini` in the working directory. By default,
errors go to `ddns_update.log` there; `--no-log` disables file logging. Configuration
errors and dry runs do not open the log. A log-open failure blocks all updates.
Log handles close after each CLI invocation. Raw exception strings, section names,
adapter prints, and provider bodies are withheld by the CLI. The repaired
adapters also emit controlled exceptions on direct calls.
Direct calls still bypass CLI logging and service-level configuration validation.

| Exit code | Meaning |
| --- | --- |
| 0 | Valid dry run, or every real-run adapter returned without raising |
| 1 | Adapter-loading, runtime, or logging failure |
| 2 | Invalid/unreadable configuration or command-line arguments |

The repaired adapters now return explicit acceptance only after their response checks
pass, and rejected/malformed responses produce code 1. Acceptance does not verify
DNS propagation. All active adapters now raise controlled failures on rejection
or unrecognized responses, but several response contracts still need live
confirmation. A failure exit also does not prove DNS stayed unchanged.
See [provider repair status](PROVIDERS.md).

Use `python -m ddns_updater` for the same CLI. The legacy
`providers.ddns_provider.main()` function delegates to this validated entry point.
A separate [scheduler dry run](SCHEDULER.md) validates daily trigger plans. Explicit named installation/removal modes are available in 0.1.0a2; ordinary
schedule() calls remain blocked. See [alpha scope](ALPHA.md).

## YDNS configuration correction

The documented YDNS API needs `hostname`, `username`, and `password` (API-v1
credentials), not a numeric domain ID and standalone API key. Existing `domain_id`
can alias `hostname` only when it contains the host name; `api_key` can alias
`password`, and `api_username` can alias `username`. Preferred keys take precedence.
The old two-key configuration cannot supply the required authentication username
and fails validation before any requests. Numeric domain IDs are also rejected.
Use a hostname such as example.ydns.io and credentials from the YDNS API page.
`record_id` optionally selects a specific record while hostname remains required.
Use a positive ASCII decimal identifier, at most 20 digits (a local input bound,
not a documented provider maximum). Invalid or blank values fail before requests.
Do not use a record ID as the hostname.

## GoDaddy and Google Domains corrections

GoDaddy now requires an explicit `hostname` (relative record name, e.g. @ or www)
in addition to the existing api_key/api_secret/domain settings. It replaces all
A records **at that name** with one IPv4 value and TTL 600, preserving other names
and record types. This is unsuitable for a multi-value A-record set you need to
retain. The old domain-wide A-record replacement is no longer used. Missing
hostname fails validation before any requests. Classic key/secret authentication
is retained for the v1 API. Explicit PAT/v3 configuration is available on main,
as described below.

GoogleDomains is unavailable for both dry-run and real-run configurations.
Migrated Google Domains no longer supports DDNS according to Squarespace. The
class remains discoverable, but rejects before network access. Select a supported
provider rather than reusing old Google credentials or assuming a Squarespace
API replacement exists. No DNS or registrar migration is performed by this tool.

## FreeDNS / Afraid migration

For either class name, use `api_key` (only the portion after `?` in the provider's
API-v1 Direct URL) and its associated `hostname`. Afraid's username/password-only
configuration now fails validation before requests. FreeDNS retains its setting
names but sends the key in the documented direct-update query, not a Bearer
header. Do not paste a complete URL or a v2 sync key. See [PROVIDERS.md](PROVIDERS.md)
for response-evidence limits and the provider's linked-update behavior.

## ClouDNS and DNSMax

`CloudNS` now requires `api_key` and `hostname`. Activate DynamicURL for the A
record in ClouDNS and copy only its `q` value into `api_key`. Do not use your
account password or paste the entire URL. `hostname` identifies the record for
your configuration; the key selects the actual record and must correspond to it.
Username/password-only configurations fail before any requests. The fixed IPv4
endpoint receives encoded `q` and `ip` parameters; exact OK indicates acceptance.

`DNSMax` is retained for a clear migration error, but both normal and dry runs
reject it with code 2 before logging or requests. The provider announced closure
on January 27, 2026. Choose and configure another provider separately; this tool
does not migrate zones. See [PROVIDERS.md](PROVIDERS.md) for sources and limits.

## EntryDNS and EuroDynDNS

`EntryDNS` now requires `token` and `hostname`. Use the record-specific token for
an A record; old username/password-only configurations fail before requests.
The token selects the record, while hostname is a configuration label and must
correspond to it. The adapter uses the provider's documented HTTPS GET endpoint
with an explicit IPv4. TLS certificate verification remains enabled.

`EuroDynDNS` retains `username`, `password`, and `hostname` and now uses the
provider's documented HTTPS update endpoint with Basic authentication. Only
exact good/nochg status, optionally followed by the requested IPv4, is accepted.
Repeated nochg updates can trigger abuse; the CLI persists a stop after abuse
and supports accepted-update change detection. See [persistent state](UPDATE_STATE.md). Explicit native task installation is available in 0.1.0a2; EuroDNS live
provider validation remains outstanding.

## Required state options for normal updates

Every active bundled provider requires both `--state-file /absolute/path/state.json`
and `--refresh-seconds N` before normal requests. Missing options return code 2.
The parent directory must exist and be controlled by the user; choose a refresh
interval appropriate for the provider. There is no universally verified default.
Dry-run needs neither option and does not inspect state usability. See
[update controls and recovery](UPDATE_STATE.md) and [alpha limits](ALPHA.md).

## GoDaddy v3 migration on main

Version 0.1.0a1 was v1-only. Version 0.1.0a2 accepts explicit v3 configuration:

```ini
[godaddy-record]
ddns_provider = GoDaddyDDNS
api_version = v3
pat = evaluation-only-token
domain = example.org
hostname = @
record_id = evaluation-only-record
ttl = 600
```

This example is dry-run only. Obtain the real PAT and record ID from your account;
never share them in issues or chat. Use a token authorized for domains.dns:update.
Domain is the punycode zone; hostname is the relative record name. Verify that the
record ID belongs to that zone and is the intended A record. TTL defaults to 600
and must be 600–86400. Record IDs accept ASCII letters/digits/underscores/hyphens
up to 256 characters, a conservative client input bound. V3 replaces only that
record with configured name/type=A/data/TTL; other writable fields are not preserved.
It does not list, create, delete records, or migrate credentials automatically.

V3 accepts only HTTP 200 with matching recordId/name/type/data/TTL JSON. Rejected
or unconfirmed results persist a stop. V1/v3 share the same provider-wide error
identity; migration requires investigating and explicitly clearing existing stops.
API-version/record/TTL/credential changes invalidate accepted-update cache identity.
Classic settings continue to select v1 when api_version is omitted. Mixing v1
credentials into v3 does not supply a PAT. Live access and propagation are unverified.
