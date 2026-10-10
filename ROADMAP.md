# Alpha release work

Implemented: provider loading/configuration validation; fourteen active adapters
with offline-tested request/response checks; two retired adapters disabled;
persistent acceptance caching, provider stops/cooldowns, and shared transport
backoff. Linux/macOS/Windows daily scheduler previews are implemented; native
installation remains blocked.

Release preparation: source/wheel packaging and installed-wheel offline checks
are implemented for candidate 0.1.0a1. Reconcile docs, verify distribution checks
and CI, and prepare a GitHub prerelease with the scope in [ALPHA.md](docs/ALPHA.md).
PyPI publication is on hold.

After alpha: controlled live provider/propagation validation, provider-specific
response/retry evidence gaps, No-IP client approval, GoDaddy PAT/v3 migration,
record-key/linked-update scope confirmation, and native scheduler integration.
Global discovery controls, total request deadlines, IPv6, environment credentials,
and automated state recovery are not implemented. Do not infer production or
unattended readiness from passing offline tests.

CI must never change DNS or install real system tasks.

## Development toward 1.0

Explicit named Linux user-crontab install/remove is implemented on main with
mocked native-command regression tests. The 0.1.0a1 tag remains unchanged.
Native cron execution/environment validation, macOS/Windows registration,
provider evidence gaps, and controlled live validation remain 1.0 release gates.

Explicit macOS user-agent install/remove is implemented on main with mocked
launchctl/file regression checks. Actual registration/execution on macOS remains
unvalidated; Windows native registration and provider/live gates remain for 1.0.

Explicit Windows current-user interactive registration/removal is implemented on
main, with mocked task commands and Windows-only PowerShell parsing in CI.
Native execution on all platforms and provider integration gaps remain for 1.0.

YDNS optional API-v1 record_id selection is implemented and validated before
requests. Acceptance identities include selection changes. Live account/record
association remains a validation gate; this does not establish live interoperability.

GoDaddy explicit PAT/v3 single-record replacement is implemented on main, retaining
v1 compatibility and shared persistent stops. Live token scope/access and record
association remain gates; the published alpha is unchanged.
