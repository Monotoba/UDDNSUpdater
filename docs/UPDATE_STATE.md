# Accepted-update state foundation

`update_state.py` provides an offline local state store. It is not connected to
the DDNS CLI yet: no updates are skipped and provider cooldowns are not enforced.
This foundation must not be taken as readiness for unattended operation.

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
address, and integer Unix timestamps. Service identity derivation and CLI options
are not implemented. Keys must distinguish provider/record/account/configuration
changes before integration; reusing a key across services could skip a required
update. Do not use a credential as the key. Records contain only IPv4 and accepted_at;
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
most 1000 entries; file size is bounded at 256 KiB. State errors are not yet mapped
to CLI exit behavior because integration is pending.

Saving uses a temporary file in the same directory, flush/fsync, and atomic
replacement. A failed replacement retains the previous file and attempts temporary
file cleanup. POSIX files/locks use mode 0600; Windows access depends on directory
ACLs and is not hardened here. Directory fsync is not implemented, so this is not
a guarantee against every power-loss/filesystem failure. State-file symlinks are
rejected, but the implementation is not a security boundary against an attacker
who can modify the parent directory or race filesystem operations. Use a trusted
local directory, not a shared/untrusted directory or network filesystem.

Tests cover round trips, expiry/future timestamps, competing locks, invalid data,
size/entry limits, and failed writes. Next: define service identity and opt-in CLI
integration, save only explicit provider success, then add provider-specific
error/cooldown state and controlled concurrency/recovery behavior.
