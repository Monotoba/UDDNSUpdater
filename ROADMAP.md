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
   Installation remains blocked. Repair cron/launchd/Windows definition generation
   next, reconcile the legacy Task-section format, and add persistent DDNS
   change/error controls before controlled native integration. See
   [scheduler status](docs/SCHEDULER.md).
5. **Documentation/release:** replace draft manuals with tested examples, add
   packaging and build checks, and complete controlled provider/native scheduler
   validation. Release only the scope supported by evidence.

CI must never change DNS or install real system tasks. PyPI publication is on hold.
