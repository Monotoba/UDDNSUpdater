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

Unlike traditional synchronous DDNS providers, the server returns HTTP 202 with an intent ID. The adapter polls status and returns success **only** when the server reports `applied`. A pending, rejected, malformed, or unknown result triggers the existing persistent provider stop control: no unattended second update is sent. The idempotency request ID is stable for the service, record and address, but status continuation across an interrupted process is not yet implemented. A stopped service must be investigated by an operator before resetting state and trying again.

A successful `applied` response reflects the server's journal; it does not prove public DNS propagation. Provider discovery remains IPv4-only. Keep this deployment local and experimental.
