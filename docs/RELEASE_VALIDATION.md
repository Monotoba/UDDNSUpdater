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

### Packaged execution probe

Main includes `python -m UTaskScheduler.execution_probe`. Create a private,
user-owned output directory, then first run this manually using the absolute
Python executable that will run the task:

```sh
/absolute/path/to/python -m UTaskScheduler.execution_probe --output-directory /absolute/path/to/probe-output -- "two words" "quote\"here" "plain-punctuation_+"
```

Pass the same executable/module/arguments to the scheduler's explicit install
mode as its command after `--`. Use platform-appropriate command-line quoting;
the example above uses POSIX shell quoting. Windows previews reject percent
characters in arguments, so choose supported punctuation for Windows checks.

Each execution writes a new `uddns-probe-*.json` with UTC timestamp, process ID,
platform/Python version, executable, working directory, and exact test arguments.
The probe makes no network requests and does not install or remove tasks. It
records no environment variables. Arguments are recorded verbatim: use harmless
strings only. A record proves the probe ran, not that a scheduled trigger caused
it; correlate timestamps with the native scheduler's execution history and the
chosen trigger. Remove manual-run records before observing the scheduled run.

The output directory must already exist, be absolute, and not itself be a
symlink. Parent directories must be trusted. Files are exclusive and mode 0600
on POSIX; Windows confidentiality depends on the directory's ACLs. Write failures
return exit code 1 with a fixed message. Inspect output manually for missing or
partial records after interrupted runs. Remove the task before deleting evidence.

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

## Optional live DuckDNS workflow

`Live DuckDNS integration` is a manual workflow on main. Routine push/PR tests
stay offline. Before using it, regenerate the token exposed during the initial
manual experiment and store the new value as repository Actions secret
`DUCKDNS_TEST_TOKEN` (Settings → Secrets and variables → Actions). Do not commit
it or enter it as a workflow input. The repository variable
`DUCKDNS_TEST_SUBDOMAIN` defaults to `monotoba-uddns-test`; set it to the bare
subdomain of a dedicated existing test A record if you use another hostname.

Open Actions → Live DuckDNS integration → Run workflow, selecting main. Each run
requires an authoritative baseline before writing, invokes the real updater with
protected temporary configuration/state, verifies the updated authoritative A
record, and verifies repeat suppression. It then restores and authoritatively
checks the baseline, including after ordinary errors or catchable interruption.
A single concurrency group prevents overlapping workflow runs; running jobs are
not canceled when another run is submitted. No scheduled trigger is enabled.
Use a manual run as a pre-release check until reliability is established.

The first update temporarily points the record at the GitHub runner's public IP.
Do not use this record for a real service or edit it concurrently from another
client. The token can control other records in the same account, so a dedicated
DuckDNS test account is preferable. The baseline IPv4 appears in logs to support
manual restoration; credentials and raw provider responses do not.

DNS checks poll up to twelve times, with five seconds between attempts and at
most two authoritative servers, five seconds per transport query. Server address
discovery uses bounded resolver calls and is cached for the run. The job has a
15-minute timeout. Forced termination, runner loss, a second interruption during
cleanup, or network/provider failure can still prevent restoration. If a run
fails or is canceled, inspect the record and restore the logged baseline through
the DuckDNS dashboard before rerunning. This workflow proves DuckDNS integration
only; it does not close other provider or native scheduling validation gates.
