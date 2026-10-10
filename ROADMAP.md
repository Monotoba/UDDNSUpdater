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
