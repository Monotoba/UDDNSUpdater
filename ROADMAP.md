# Development toward 1.0

The published [0.1.0a1 alpha](docs/ALPHA.md) provides offline-tested IPv4 provider
updates, persistent acceptance/error state, daily scheduler previews, and source/
wheel packaging. PyPI publication remains on hold.

Main additionally implements explicit installation/removal for Linux user cron,
macOS user launchd, and Windows current-user interactive tasks. These paths have
mocked native-command tests; Windows CI also checks PowerShell syntax. YDNS record
selection and GoDaddy PAT/v3 single-record replacement are implemented. These
changes do not alter the published alpha.

The next work is validation rather than adding more scheduler backends:

1. Resolve remaining provider response/retry evidence and No-IP identification
   requirements. Keep unverified responses fail-closed.
2. Exercise each native scheduler with a harmless local probe; confirm execution,
   argument boundaries, environment, removal, and preservation of unrelated tasks.
3. Validate providers against disposable records with authorized credentials;
   confirm request acceptance, record identity, and authoritative DNS propagation.
4. Reconcile operating documentation, build/install the candidate distribution,
   verify all six CI jobs, and publish 1.0 only after supported paths have evidence.

[RELEASE_VALIDATION.md](docs/RELEASE_VALIDATION.md) records the evidence required
and current gaps. Passing mocked tests does not establish native or provider
interoperability. CI must never change DNS or install real system tasks.

IPv6, environment-based credentials, total request deadlines, global discovery
controls, and automated state recovery are not implemented. Their absence must be
stated in release documentation rather than implied to be supported.
