# Accepted-update state foundation

`update_state.py` provides a local accepted-update state store. The DDNS CLI
now supports opt-in change detection, described below. No-IP stop/cooldown controls are implemented; other providers remain unfinished; this is not readiness for unattended operation.

```python
from update_state import open_state

# Parent directory must already exist and be controlled by the user.
with open_state("/absolute/path/to/update-state.json") as state:
    matches = state.matches(service_key, current_ipv4, now=epoch_seconds,
                            max_age=refresh_seconds)
    # Only after the provider explicitly accepts the update:
    state.record_accepted(service_key, current_ipv4, accepted_at=epoch_seconds)
    state.save()
```

The caller supplies a stable lowercase 64-digit hex service identity, an IPv4
address, and integer Unix timestamps. The CLI derives service identities as described below. Keys must distinguish provider/record/account/configuration
changes before integration; reusing a key across services could skip a required
update. Do not use a credential as the key. Acceptance records contain only IPv4 and accepted_at; error records contain only
control kind and timestamps;
no hostname, username, token, response body, or configuration is persisted by this
module. An acceptance record will mean provider acceptance, not independently
verified DNS propagation.

Matching requires the same address and an age strictly below an explicit positive
maximum age. Records from the future do not match. The module does not choose a
refresh interval or fetch time/IP itself. `record_accepted` modifies memory only;
`save` is explicit. Context exit never automatically persists changes. Failed or
unverified provider results must not call record_accepted in the future integration.

Use open_state for the entire read/update/save cycle. An exclusive .lock sidecar
blocks other cooperating writers; failure to acquire it is an error, not permission
to proceed without state. Locks are removed on normal exit and exceptions. A process
crash can leave a lock behind: stop other instances and establish that no owner is
active before manually removing it. There is no automatic stale-lock recovery.

Missing state starts empty. Corrupt, oversized, unknown-version, duplicate-key,
invalid-address, or invalid-timestamp files raise StateError without echoing data
or paths. They are not silently overwritten. The JSON format has a version and at
most 1000 acceptance entries plus 1000 error controls; file size is bounded at 256 KiB. State failures return CLI exit 1; corrupt state prevents network requests.

Saving uses a temporary file in the same directory, flush/fsync, and atomic
replacement. A failed replacement retains the previous file and attempts temporary
file cleanup. POSIX files/locks use mode 0600; Windows access depends on directory
ACLs and is not hardened here. Directory fsync is not implemented, so this is not
a guarantee against every power-loss/filesystem failure. State-file symlinks are
rejected, but the implementation is not a security boundary against an attacker
who can modify the parent directory or race filesystem operations. Use a trusted
local directory, not a shared/untrusted directory or network filesystem.

Tests cover round trips, expiry/future timestamps, competing locks, invalid data,
size/entry limits, and failed writes. CLI integration saves only explicit provider success. No-IP error/cooldown persistence is implemented. Next: other providers and
controlled recovery behavior.

## Opt-in CLI change detection

```sh
python ddns_updater.py --config-file /absolute/path/to/services.ini --state-file /absolute/path/to/update-state.json --refresh-seconds 86400
```

The 86400-second value is illustrative, not a verified refresh policy for every
provider. Choose an interval that meets your provider's current requirements;
no automatic interval is selected. --state-file and --refresh-seconds must be
provided together. The path must be absolute, its parent must already exist, and
it must differ from the configuration and current error-log paths. An integer
refresh interval must be positive and at most ten decimal digits. Without these
options the previous update behavior is retained for other providers. Normal
No-IP updates now require state/refresh options for persistent error controls.

The CLI validates all service configurations, then acquires/loads state before
opening its log or constructing providers. It holds the lock until all services
finish, including network requests. A competing process fails instead of updating
without state. --dry-run validates options/configuration without opening or checking
the state file, acquiring a lock, creating logs, or constructing providers; it
therefore cannot establish that the state path is usable or its contents are valid.

Each provider constructor still discovers the current IPv4 address. A matching
address with an acceptance younger than refresh-seconds skips only the provider
update request, and leaves its original timestamp unchanged. Changed addresses,
expired/future records, and missing records attempt an update. Discovery requests
are not skipped or shared between services. This feature does not query DNS or
prove propagation, and an externally changed DNS record may go unnoticed until
refresh expiry or the next address/configuration change.

Only the literal adapter result True records acceptance. False, None, other
results, and exceptions never record success. An existing record is retained on
provider failure. Accepted updates save immediately, so an unrelated later failure
does not lose earlier recorded success. Ordinary provider exceptions retain the existing
sanitized error/continue-to-next-service behavior. Typed provider stop/retry errors
persist controls and stop the current run, as described below. If saving an accepted update
fails, exit 1 explicitly reports that the provider accepted it but persistence
failed, and remaining services are not attempted. The already sent update cannot
be rolled back; retry may resend it. Unexpected adapter results retain the existing
unverified-completion message and exit behavior.

Service identity is a SHA-256 digest of versioned canonical JSON containing the
section name, provider module/class, and all normalized settings, including
credentials. Credential/account/record/section changes therefore invalidate the
cache. Sorting makes setting order irrelevant. Renaming a section can cause a
fresh update; old identities remain until state is managed explicitly and the
1000-entry limit can eventually be reached. The file contains no plaintext
credentials, but the unsalted digest is not encryption and may permit offline
credential guessing if the rest of the configuration is known. Protect the file
and its directory as sensitive local data. No identity is printed in CLI output.

Other providers still lack persistent cooldown/fatal-error handling. Automatic
stale-record pruning, shared IP discovery, and native scheduler installation also
remain unavailable. Do not run unattended until the remaining provider-specific
error controls and integration requirements are implemented and tested.
Tests use fake adapters and blocked HTTP, including changed/unchanged IP, expiry,
identity changes, unverified/failing results, corrupt/locked state, and save failures.
No live DNS update was used to validate this integration.

## No-IP stop and cooldown controls

The CLI now requires state/refresh options for normal No-IP updates; missing them
returns exit 2 before any network requests. Dry run still validates the provider
configuration without requiring or reading state. Direct adapter users must handle
the typed ProviderStopError/ProviderRetryError themselves; the library does not
open state automatically.

No-IP's [response documentation](https://developer.noip.com/reference/nic_update)
specifies a minimum 30-minute wait after 911 or HTTP 500, and intervention for
stop responses. The adapter raises ProviderRetryError(1800) for these temporary
failures, and ProviderStopError for nohost, badauth, badagent, !donator, abuse,
unconfirmed/malformed update bodies, or other rejected HTTP statuses. Treating
unknown responses/statuses as stops is a conservative client policy, not a claim
that No-IP prescribes identical handling for every HTTP code. Multi-host responses
are checked for errors before result-count validation; any error prevents recording
whole-request acceptance. A stop response takes priority over 911 in mixed output.

On either typed error the CLI records the control, saves immediately, returns 1,
and does not attempt remaining services during that run. A failed error-state save
also stops with a controlled persistence error. Existing accepted records are
preserved. On subsequent invocations a control is checked before constructing the
provider, so neither IPv4 discovery nor updates are sent for blocked services.
Blocked services report a sanitized error and exit 1; other unblocked providers
may proceed on that subsequent run. File logs receive the same sanitized messages.

Controls conservatively cover every No-IP section/account using this state file.
Changing hostname, section, credentials, or user_agent does not bypass a control.
This deliberately blocks more than an individual record when an error is local;
it avoids guessing error scope. Separate state files/processes/direct adapters
cannot share these controls and can bypass them; do not use those to circumvent a
provider stop. Stop records never automatically expire. Cooldowns unblock at
recorded_at+1800, measured with wall-clock Unix time. Backward clock changes keep
them blocked; forward jumps can shorten the real elapsed wait. Correct system time
is required, and cross-restart monotonic elapsed time is not guaranteed.

After investigating and correcting a stop cause, with updater processes stopped,
a user can deliberately clear only the No-IP control through the Python API:

```python
from update_state import open_state
from ddns_updater import provider_error_key
from providers.provider_noip import NoIP

with open_state("/absolute/path/to/update-state.json") as state:
    state.clear_error(provider_error_key(NoIP, {}))
    state.save()
```

Do not clear an unexpired outage cooldown to retry early. This manual operation
preserves acceptance records. There is no automatic stop reset. A successful
No-IP update after an expired cooldown clears that provider's error record.

State writers now emit version 2 with an errors dictionary. Version 1 acceptance
files load with empty error controls and upgrade on the next explicit save. Older
application versions cannot read version 2 and must not be used to bypass controls.
Invalid/unknown error records fail closed; no raw provider responses are stored.

Transport/IP-discovery exceptions remain ordinary sanitized failures and do not
yet get persistent backoff. No-IP User-Agent approval, current account/DDNS-key
requirements, live response behavior, and other providers remain release blockers.
Tests use mocked HTTP for 911/500, permanent stops, mixed responses, restart
blocking before discovery, expiry, configuration-change bypass attempts, and v1
migration. No live DNS updates were performed.
