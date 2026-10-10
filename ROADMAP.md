# Development toward 1.0

The published [0.1.0a1 alpha](docs/ALPHA.md) provides offline-tested IPv4 provider
updates, persistent acceptance/error state, daily scheduler previews, and source/
wheel packaging. PyPI publication remains on hold.

Main additionally implements explicit installation/removal for Linux user cron and systemd timers,
macOS user launchd, and Windows current-user interactive tasks. These paths have
mocked native-command tests; Windows CI also checks PowerShell syntax. YDNS record
selection and GoDaddy PAT/v3 single-record replacement are implemented. These
changes do not alter the published alpha.

Linux cron, systemd user timers, macOS launchd and Windows Task Scheduler have
passed disposable-runner scheduled-execution and cleanup checks. Windows testing
found and resolved account-name/SID and omitted-default run-level export
differences. Systemd uses the same daily planner as cron. User-specific session,
sleep, reboot and DST environments remain separate checks.

The next work is validation:

1. Resolve remaining provider response/retry evidence and No-IP identification
   requirements. Keep unverified responses fail-closed.
2. Retain the successful native scheduler probes as manual pre-release checks;
   validate additional session/platform behavior where it is advertised.
3. Validate providers against disposable records with authorized credentials;
   confirm request acceptance, record identity, and authoritative DNS propagation.
4. Reconcile operating documentation, build/install the candidate distribution,
   verify all six CI jobs, and publish 1.0 only after supported paths have evidence.

[RELEASE_VALIDATION.md](docs/RELEASE_VALIDATION.md) records the evidence required
and current gaps. Passing mocked tests does not establish native or provider
interoperability. Routine push/PR CI stays offline and never installs native tasks. Separate manual
live workflows use disposable DNS records or hosted-runner tasks explicitly.

IPv6, environment-based credentials, total request deadlines, global discovery
controls, and automated state recovery are not implemented. Their absence must be
stated in release documentation rather than implied to be supported.
