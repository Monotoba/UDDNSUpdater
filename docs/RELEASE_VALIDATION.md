# 1.0 release validation

This checklist applies to main, not the published 0.1.0a1 alpha. An implemented
path is not a verified integration. Record candidate commit, date, platform,
Python version, sanitized commands, outcomes, and cleanup for every live check.
Never record credentials, tokens, or raw provider bodies in public evidence.

## Current evidence

| Area | Implemented and tested | Evidence still required |
| --- | --- | --- |
| Linux cron | Explicit named install/remove, preservation checks, mocked commands, shell argv round trip | Real user crontab registration, daemon execution, environment, removal and unrelated-entry preservation |
| macOS launchd | Explicit user-agent registration/removal, plist validation, mocked commands | GUI-domain registration, actual launchctl error behavior, scheduled execution, removal |
| Windows tasks | Explicit current-user registration/removal, ownership checks, mocked commands, PowerShell syntax in Windows CI | Real registration/export, interactive execution and environment, removal, unrelated-task preservation |
| Providers | Fourteen active adapter classes, controlled request/response errors and persistent state | Provider-specific contract gaps in PROVIDERS.md; disposable-record acceptance and propagation |
| YDNS | Optional record_id selection | Account-to-record association and selected-record update |
| GoDaddy | Classic v1 and PAT/v3 single-record update | PAT scopes, existing record identity, v3 response and propagation |
| Distribution | Source/wheel builds, isolated installed-wheel offline checks in six CI jobs | Repeat on final candidate; verify documented commands against installed package |

## Native scheduler checks first

Use a separate named task and a harmless script that writes a timestamp and
received arguments to a user-owned temporary directory. Use absolute paths and
include arguments containing spaces and punctuation. Do not run the DNS updater
for this stage.

1. Save a sanitized inventory of existing tasks and choose an unused name.
2. Preview the definition; install through the explicit CLI mode documented in
   SCHEDULER.md. Confirm the registered definition, identity, and daily triggers.
3. Observe a scheduled run in the intended login/session environment. Check the
   timestamp, argument boundaries, executable, and working-directory assumptions.
   A manual launch alone does not prove scheduled execution.
4. Remove through the matching CLI mode. Confirm the task is absent and unrelated
   tasks are unchanged. Retain failure evidence and inspect partial state before
   retrying installation; do not overwrite a colliding task.

## Provider checks after scheduler checks

Use disposable A records with explicit authorization for DNS writes. Establish
which record a token selects before sending an update, including FreeDNS linked
records and GoDaddy's v1 record-set replacement scope. Keep credentials in
protected configuration files. Verify No-IP's current client identification
requirements before that integration check.

1. Record the current authoritative A value and the intended update address.
2. Run a single update with a separate protected persistent state file. Confirm
   sanitized CLI success and acceptance state; query authoritative DNS for the
   intended record and check unrelated records where the API can affect them.
3. Repeat with the same address within the configured refresh window. Verify
   acceptance caching suppresses the update without claiming propagation checks
   are part of the adapter itself.
4. Exercise rejection/cooldown behavior with offline fixtures. Do not deliberately
   trigger provider abuse protections in live accounts. Restore disposable records
   if necessary and remove the test task/configuration after the check.

## Release decision

All advertised integrations need evidence or an explicit reduced support scope
before 1.0. Keep unresolved response contracts and live failures visible. Passing
CI does not close these gaps. Run the full suite and distribution checks on the
final candidate, reconcile README/provider/scheduler instructions, and record
known limits before creating the tag. PyPI publication remains a separate task.
