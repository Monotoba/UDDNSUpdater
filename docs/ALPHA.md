# Alpha candidate 0.1.0a1

This candidate supports experimental IPv4 CLI updates with persistent controls
and offline scheduler previews. It does not establish live provider interoperability,
DNS propagation, production readiness, or unattended scheduling support. No release
has been published yet; PyPI publication remains on hold.

## Installation and offline evaluation

Use Python 3.10+ in a virtual environment. From a source checkout or extracted
source archive:

```sh
python -m venv .venv
# Linux/macOS:
. .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
python -m pip install .
uddns-updater --help
uddns-updater --config-file examples/evaluation.ini --dry-run
```

The example has fictitious credentials and is only for dry-run. Help and dry-run
send no requests and write no logs/state. Distribution installs also support
`python -m ddns_updater`. Configuration files are not installed as live defaults.
An installed wheel requires Requests; ordinary pip installation resolves it.

For real updates, use a protected INI file, a trusted existing local state directory,
and both state options. Choose the refresh interval using the provider's policy;
there is no verified universal interval. Read [CLI.md](CLI.md),
[PROVIDERS.md](PROVIDERS.md), and [UPDATE_STATE.md](UPDATE_STATE.md) first.
A real run can change DNS, even when a later response or state write fails.

## Scope

| Feature | Alpha evidence and limits |
| --- | --- |
| Provider updates | Fourteen active adapter classes tested with mocked HTTP; GoogleDomains/DNSMax disabled; retired changeip.com targets rejected |
| Update state | Accepted IPv4 cache; provider-scoped stops/cooldowns; atomic local saves and exclusive locks; explicit recovery |
| Transport | 30-minute client-policy cooldown for Requests errors and rejected discovery HTTP; provider-scoped rather than globally scoped to ipify |
| Scheduling | Offline daily cron, launchd, Windows XML, and legacy TaskN planning; native installation blocked |
| Installation | Source/wheel build and installed-wheel entry-point checks outside checkout; Python 3.10/3.12 CI on Linux, Windows, Intel macOS |

Known gaps include live credentials/response/propagation validation, several complete
provider response/retry specifications, No-IP client identification approval,
GoDaddy PAT/v3 migration, FreeDNS linked-update scope, and record-key associations.
GoDaddy v1 replaces the named A-record set with one address. No IPv6 support or
DNS propagation verification is implemented. State limits, crash locks, trusted
parent directories, Windows ACLs, and wall-clock expiry require review before use.

## Release verification

```sh
python -m pip install -r requirements-dev.txt build
python -m pytest -q
python -m build
python tools/check_distribution.py dist/uddnsupdater-0.1.0a1-py3-none-any.whl
```

The distribution check installs the wheel outside the checkout and prohibits HTTP
while verifying console/module help, dry-run, provider discovery, and packaging
contents. The source archive includes docs, offline examples, tests, and this check.
GitHub's generated source archives and Python source distributions have a single
project directory. No tests contact live DNS providers or install native tasks.
