# UniversalDDNSServer provider (pre-alpha)

The `UniversalDDNSServer` provider connects to an explicitly configured **local loopback** UniversalDDNSServer API. This initial implementation intentionally refuses remote URLs until a documented TLS trust policy is implemented.

Example `config.ini` service section:

```ini
[HomeServer]
ddns_provider = UniversalDDNSServer
base_url = http://127.0.0.1:8765
record_id = home
token = REPLACE_WITH_SCOPED_BEARER_TOKEN
```

The token requires `records:write` and `intents:read` scopes and access to `home`. Use `--state-file /absolute/path/to/state.json --refresh-seconds 3600` to enable durable acceptance and conservative stop controls.

Unlike traditional synchronous DDNS providers, the server returns HTTP 202 with an intent ID. The adapter polls status and returns success **only** when the server reports `applied`. A pending, rejected, malformed, or unknown result triggers the existing persistent provider stop control: no unattended second update is sent. The idempotency request ID is stable for the service, record and address, and the CLI now persists a returned intent ID before polling. A later run using the same state file resumes with status GET requests rather than submitting a second PUT. When the old address is still unresolved, a changed discovered address is rejected. Pending outcomes still demand conservative handling. The narrow crash window between server acceptance and persistence of its intent ID remains: a subsequent request reuses the deterministic request ID for server-side idempotency, but can issue a second HTTP PUT. Do not erase state to force a retry; inspect unresolved operations first.

A successful `applied` response reflects the server's journal; it does not prove public DNS propagation. Provider discovery remains IPv4-only. Keep this deployment local and experimental.
