# Alpha 0.1.0a2

This experimental alpha adds explicit native scheduler installation/removal,
YDNS record selection and GoDaddy PAT/v3 updates. DuckDNS and all four scheduler
backends have controlled live evidence. Other providers remain offline-tested,
and this release is not a claim of general production or unattended readiness.
See [GitHub releases](https://github.com/Monotoba/UDDNSUpdater/releases) for source
archives. PyPI publication remains on hold. The earlier 0.1.0a1 is unchanged.

## Installation and offline evaluation

Use Python 3.10+ in a virtual environment. From a source checkout of tag
`v0.1.0a2` or its extracted source archive:

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

## Scope and evidence

| Feature | Evidence and limits |
| --- | --- |
| Provider updates | Fourteen active adapter classes tested with mocked HTTP; GoogleDomains/DNSMax disabled; retired changeip.com targets rejected |
| DuckDNS | Real CLI acceptance, authoritative A visibility, repeat suppression and verified restoration on one authorized test record; see [live evidence](LIVE_VALIDATION.md) |
| Record selection | YDNS optional record_id and GoDaddy PAT/v3 single-record replacement are implemented and offline-tested; live entitlement and record/account association remain unverified |
| Update state | Accepted IPv4 cache; provider-scoped stops/cooldowns; atomic local saves and exclusive locks; explicit recovery |
| Transport | HTTPS with redirects disabled and bounded connect/read waits; 30-minute client-policy cooldown for Requests errors and rejected discovery HTTP, provider-scoped rather than global to ipify |
| Scheduling | Explicit user cron/systemd installation on Linux, GUI-user launchd on macOS, and current-user interactive tasks on Windows; scheduled execution and cleanup passed on disposable hosted runners |
| Installation | Source/wheel build and installed-wheel entry-point checks outside checkout; Python 3.10/3.12 CI on Linux, Windows and Intel macOS |

## Known shortcomings

- Providers other than DuckDNS have no live acceptance or authoritative DNS
  evidence. Several complete response/retry contracts remain unconfirmed.
- No-IP's default identifier is a prototype; no provider approval/certification
  outcome is recorded. A printable-ASCII override alone does not prove approval.
- FreeDNS linked updates can affect other records. GoDaddy v1 replaces the named
  A-record set with one address. Tokens, record IDs, PAT scopes and account
  entitlements require provider-specific verification before writes.
- IPv6 is not implemented. Production adapters do not verify DNS propagation;
  only the separate manual DuckDNS harness does so.
- Schedulers support daily plans, not arbitrary cron expressions. Actual tests
  cover Ubuntu 24.04, macOS 15 Intel GUI sessions and Windows hosted-runner
  interactive sessions. Logout/linger, sleep/resume, reboot, DST, battery/idle
  defaults and other user/distribution environments remain unverified.
- Native registration/removal can leave partial state after failures. Inspect
  managed definitions and recover explicitly; do not overwrite colliding tasks.
  General schedule() calls remain blocked; native mutation requires explicit modes.
- Use absolute paths and a writable log location or --no-log for scheduled DDNS.
  The scheduled working directory is platform-specific, not the checkout.
- State files need trusted parent directories and appropriate Windows ACLs.
  Crash locks require manual recovery; expiry uses wall-clock time. Environment
  credentials, global discovery controls and automated state recovery are absent.
- HTTP connect/read timeouts are not a total deadline. Response-size checks occur
  after download and are not a streaming memory bound. Live cleanup cannot be
  guaranteed after forced termination, runner loss or network/provider failure.

See [release evidence and remaining 1.0 gates](RELEASE_VALIDATION.md). Passing CI
and one live provider check do not establish all-provider interoperability.

## Release verification

```sh
python -m pip install -r requirements-dev.txt build
python -m pytest -q
python -m build
python tools/check_distribution.py dist/uddnsupdater-0.1.0a2-py3-none-any.whl
```

The distribution check installs the wheel outside the checkout and prohibits HTTP
while verifying console/module help, dry-run, provider discovery, and packaging
contents. The source archive includes docs, offline examples, tests, and this check.
GitHub's generated source archives and Python source distributions have a single
project directory. Routine tests never contact live DNS providers or install native
tasks. Separate manually dispatched live workflows exercise disposable records/tasks.
