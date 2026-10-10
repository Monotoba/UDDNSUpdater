Experimental alpha for IPv4 dynamic-DNS updates and explicit user task scheduling. Intended for evaluation and contributor testing; remaining provider and unattended-use gaps prevent a 1.0 production-readiness claim.

## Changes since 0.1.0a1

- Explicit named installation/removal for Linux user cron and systemd timers, macOS GUI-user launchd, and Windows current-user interactive tasks. Linux adds scheduler selection and managed status commands.
- YDNS optional record_id selection and GoDaddy PAT/v3 single A-record replacement, with offline request/response and configuration validation.
- Packaged execution probe and manual hosted-runner integration workflows, plus corrected operating documentation and provider evidence.
- Windows native identity verification handles account-name/SID forms and verified least-privilege defaults in exported tasks.

## Validation

- Local suite: 1,265 passed, four platform-specific skips.
- Six CI configurations: Linux, Windows and Intel macOS with Python 3.10/3.12, including source/wheel builds and isolated installed-wheel offline checks.
- [DuckDNS live check](https://github.com/Monotoba/UDDNSUpdater/actions/runs/38022228218): real CLI update, authoritative A verification, repeat suppression and authoritatively verified restoration on one authorized test record.
- Native scheduled execution and cleanup passed for [Linux cron](https://github.com/Monotoba/UDDNSUpdater/actions/runs/38025262434), [Linux systemd](https://github.com/Monotoba/UDDNSUpdater/actions/runs/38027896157), and [Windows/macOS](https://github.com/Monotoba/UDDNSUpdater/actions/runs/38028091981). These earlier checks cover the unchanged runtime implementation used in this release; the final candidate changes version metadata and documentation.

## Install and evaluate

Extract the source archive below. In an activated Python 3.10+ virtual environment:

```sh
python -m pip install .
uddns-updater --help
uddns-updater --config-file examples/evaluation.ini --dry-run
```

The example has fictitious credentials. Help/dry-run do not contact providers or write state/logs. Real updates require protected provider settings, --state-file and --refresh-seconds; select the interval according to provider policy. Read docs/ALPHA.md, docs/CLI.md, docs/PROVIDERS.md and docs/UPDATE_STATE.md before writes. Native installation requires an explicit scheduler mode; use absolute paths and a writable log location or --no-log.

## Known shortcomings

- DuckDNS is the only live-validated provider, on one account/record. Other adapters have offline tests, with some incomplete response/retry specifications and unverified record/token associations. GoogleDomains and DNSMax are disabled.
- No-IP uses a prototype default identifier; no client approval/certification outcome is recorded. A configured override does not establish approval.
- YDNS selected-record association and GoDaddy PAT scopes/v3 live access remain unverified. GoDaddy v1 replaces the configured named A-record set with one address. FreeDNS linked updates may affect other records; check account settings first.
- IPv4 only. Production adapters do not verify DNS propagation; the separate DuckDNS test harness does. No environment-based credentials or total HTTP request deadline; body-size checks occur after download.
- Daily scheduler plans only. Live evidence covers Ubuntu 24.04, macOS 15 Intel GUI sessions and Windows hosted-runner interactive sessions. Other distributions/session environments, logout/linger, reboot, sleep/resume, DST and battery/idle behavior remain unverified. Windows requires the user to be logged on; macOS requires an active GUI domain.
- Native failures can leave partial managed state. State files need trusted parent directories and appropriate Windows ACLs; crash locks require manual recovery and expiry depends on wall-clock time. Discovery cooldowns are provider-scoped, not global to ipify. Automatic state recovery is absent.
- Real DNS writes can occur before a later failure. Forced termination, runner loss or network/provider failures can prevent live-test restoration. Routine CI stays offline and never registers tasks.

See docs/RELEASE_VALIDATION.md for remaining 1.0 gates. BSD-2-Clause. PyPI publication remains on hold.
