# Repair order

1. **Implemented baseline:** fix shared provider imports and working-directory-independent
   discovery; document the prototype accurately; add offline tests and CI.
2. **Implemented CLI/configuration baseline:** validate missing files/sections/provider keys before
   network access; disable interpolation for literal credentials; introduce a
   side-effect-free dry run, explicit config path, sanitized errors, and reliable
   nonzero statuses for configuration and raised runtime failures. Existing
   provider classes/config keys are preserved. Adapters that only print failures
   remain a blocker for verified provider success in step 3.
3. **Provider requests:** validate IPv4 discovery, add timeouts and redirect rules,
   encode parameters, and verify provider-specific success bodies. Audit each
   adapter against current official documentation; do not claim all adapters
   work from shared HTTP status checks. Test request/response contracts offline.
   **Partial:** shared IPv4 discovery is repaired; the repaired adapters use encoded
   parameters, timeouts, redirect blocking, and explicit response checks. All 16
   classes have been audited: 14 active adapters repaired, 2 retired services
   disabled. Full response specifications and live validation remain outstanding
   for several services; persistent change/error controls are also unfinished.
4. **Scheduler, partial:** unified daily hour/minute validation and planning-only
   dry run are implemented, with argument boundaries preserved and no native writes.
   Linux, macOS, and Windows definition previews and legacy Task-section daily
   planning are implemented; installation remains blocked. Add persistent DDNS
   change/error controls before controlled native integration. See
   [scheduler status](docs/SCHEDULER.md).
5. **Documentation/release:** replace draft manuals with tested examples, add
   packaging and build checks, and complete controlled provider/native scheduler
   validation. Release only the scope supported by evidence.

CI must never change DNS or install real system tasks. PyPI publication is on hold.

Scheduler progress: Linux cron and macOS launchd previews are implemented and
installation remains blocked. Windows XML previews are also implemented; native integration remains unvalidated.

Windows preview: explicit start date, maximum 48 daily triggers, and offline
XML/argument validation. Next: reconcile the legacy Task-section parser.

Task-section daily planning now preserves JSON argument lists and rejects
unsupported dates/calendar restrictions. Next: persistent DDNS change/error controls.

Persistent-state foundation: versioned accepted IPv4/timestamp records, bounded
validation, exclusive locks, and atomic writes are implemented offline. CLI
identity/skip integration is implemented; provider cooldowns remain unfinished; see
[update state](docs/UPDATE_STATE.md).

Opt-in state integration skips recently accepted unchanged IPv4 addresses and
saves only explicit adapter success. Refresh policy is caller-supplied. Persistent
provider error/cooldown controls are the next step.

No-IP now persists provider-wide stop controls and 30-minute 911/HTTP-500
cooldowns, checked before discovery. State v1 migrates on save to v2. Other
providers, transport backoff, and controlled live validation remain unfinished.

Dynu now persists provider-wide stop controls and ten-minute retry controls for
911/servererror/dnserr (the latter two use a conservative client delay). HTTP
rejections require review. No-IP and Dynu both require state options for normal
CLI updates; other providers and transport backoff remain unfinished.

SecurePoint/SpDYN share a persistent conservative stop identity across both names.
Normal CLI updates require state options; retry timing remains unverified because
the official response-code page is access-blocked. No cooldown interval is guessed.
Other providers and transport backoff remain unfinished.
