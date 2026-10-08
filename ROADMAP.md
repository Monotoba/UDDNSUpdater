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
4. **Scheduler:** reconcile existing interfaces, validate schedule fields, fix
   cron/launchd/Windows command generation, and avoid shell interpolation.
   Test with mocked subprocesses and temporary files before native integration.
5. **Documentation/release:** replace draft manuals with tested examples, add
   packaging and build checks, and complete controlled provider/native scheduler
   validation. Release only the scope supported by evidence.

CI must never change DNS or install real system tasks. PyPI publication is on hold.
