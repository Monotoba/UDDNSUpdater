# Provider repair status

Reviewed on 2026-10-08. All validation below is offline with mocked HTTP. No
live updates or DNS propagation checks have been performed. No release is available.

| Component | Implemented checks | Outstanding work |
| --- | --- | --- |
| Shared IPv4 discovery | HTTPS ipify IPv4 endpoint; strict IPv4 parsing; HTTP 200 required; redirects disabled; connect/read timeouts | Controlled live check |
| NamecheapDDNS | Encoded parameters; same HTTP rules; XML structure, zero error count, Done=true, matching IP, no error entries; rejects malformed/duplicate required fields and DOCTYPE | Controlled live response/propagation validation |
| DuckDNS | Encoded domains/token/IP; same HTTP rules; exact OK response without verbose mode | Controlled live acceptance/propagation validation |
| NoIP | HTTPS Basic authentication; encoded hostname/IP; client-identifying User-Agent; good/nochg plus matching IPv4 for each hostname | Approved client identification, transport backoff, controlled live validation (state required for CLI stop/cooldown controls) |
| Dynu | HTTPS Basic authentication; encoded hostname/IP; myipv6=no; exact good/nochg status with matching IP when supplied; persistent stop/retry controls | Transport backoff, controlled live validation (state required for CLI controls) |
| ChangeIP | HTTPS Basic auth; encoded parameters; known plain-text success heading, matching IP when present | Provider response documentation/controlled live confirmation |
| SecurePoint | Corrected HTTPS endpoint; Basic auth; encoded parameters; good/nochg checks; persistent conservative stops | Full wiki access, retry policy, transport backoff, controlled live confirmation |
| SpDYN | Reuses SecurePoint and shares its persistent stop identity | Same wiki/retry-policy/live-validation limitations as SecurePoint |
| YDNS | Documented trailing-slash HTTPS endpoint; host/IP parameters; Basic auth; exact good response; corrected credential settings with legacy aliases | Controlled live validation; optional record_id selection not implemented |
| GoDaddyDDNS | Scoped v1 PUT by domain/type/name; explicit hostname; encoded paths; key/secret auth; shared HTTP protections; empty 200/204 acceptance | Controlled live validation; PAT/v3 migration; named multi-value A sets are replaced |
| GoogleDomains | Disabled before network access; retained discoverable class and migration error | Service unavailable for migrated domains |
| Afraid / FreeDNS | Shared API-v1 direct update key; encoded address; shared HTTP protections; conservative hostname/IP response checks | Controlled live response confirmation; account linked-update scope; v2 not implemented |
| CloudNS | Documented IPv4 DynamicURL endpoint; encoded per-record q key and ip; shared HTTP protections; exact OK response | Controlled live acceptance/propagation validation; optional JSON/failover parameters not implemented |
| DNSMax | Disabled before network access; retained class with migration errors | Provider closed January 27, 2026 |
| EntryDNS | Documented per-record HTTPS GET; encoded token path and explicit ip; shared HTTP protections; exact OK policy | Provider response specification/controlled live confirmation; token-to-hostname association not verified |
| EuroDynDNS | Documented HTTPS update endpoint; encoded hostname/myip; Basic auth; single good/nochg status with matching IPv4 when present | Persistent change/error controls; controlled live response/propagation validation |

The shared discovery endpoint is `https://api.ipify.org`. It returns an IPv4
address in plain text according to [ipify's documentation](https://www.ipify.org/).
Invalid or IPv6 discovery results stop construction before provider update calls.

Namecheap uses the documented HTTPS GET endpoint with `host`, `domain`, `password`,
and `ip` parameters; `password` is the Dynamic DNS password. Preserve host/domain
case as configured in your account. Namecheap currently documents IPv4-only DDNS.
See [Namecheap's HTTPS update guide](https://www.namecheap.com/support/knowledgebase/article.aspx/29/11/how-to-dynamically-update-the-hosts-ip-with-an-https-request/)
and its [DDClient guide](https://www.namecheap.com/support/knowledgebase/article.aspx/583/11/how-do-i-configure-ddclient/).
Our conservative XML acceptance policy requires exactly one ErrCount=0,
Done=true, and matching IP beneath interface-response. This is a tested parser
policy, not a claim that live responses have been validated.

DuckDNS accepts a comma-separated list of subnames in the existing `subdomain`
setting. The implementation sends no `verbose` flag and accepts only `OK` after
stripping outer whitespace; `KO` or unexpected content raises a controlled error.
See the [official DuckDNS specification](https://www.duckdns.org/spec.jsp).

For shared discovery and the fourteen repaired update adapters, connect/read timeouts
are 5/15 seconds, not a total wall-clock deadline. Redirects and unexpected HTTP
statuses are rejected; GoDaddy also accepts an empty 204 response. Bodies are limited to 65,536 characters **before parsing**, after
Requests has downloaded them; this is not a streaming/download memory limit.
Responses are closed after use, and exceptions omit raw request URLs and bodies.
There are no retries, IPv6 updates, cache, or propagation checks.

All 16 classes have now been audited: 14 active adapter classes have repaired
request/response handling, and GoogleDomains/DNSMax are disabled. This completes
the initial source audit, not live service validation. Incomplete response
documentation, account-specific settings, and unattended-use controls remain
limitations. Do not infer complete support from class names or HTTP success.

## No-IP and Dynu

No-IP uses the [documented HTTPS endpoint and Basic authentication](https://www.noip.com/integrate/request).
Each comma-separated hostname/group must have one response line: good or nochg
followed by the requested IPv4. Unexpected counts, wrong IPs, and rejection codes
raise controlled errors. The optional `user_agent` setting overrides the prototype
identifier (Monotoba UDDNSUpdater/OS-development plus the public repository issues URL).
Only printable ASCII is allowed to prevent header injection. The default contact
URL is not an approved/certified No-IP User-Agent and does not establish compliance
with its recommended maintainer-email format. Provide an appropriate identifier
and complete approval requirements before using it as a distributed client.

No-IP specifies updates only when the IP changes and requires stopping after
errors; 911/HTTP 500 requires at least 30 minutes before another attempt.
See [response requirements](https://www.noip.com/integrate/response). The CLI now
requires persistent state options for normal No-IP updates. It records provider-wide
stop controls and 30-minute 911/HTTP-500 cooldowns and checks them before discovery
on later invocations. Section/account/configuration changes cannot bypass controls
in the same state file. Unknown responses are conservative stops; direct adapters
must handle typed errors themselves. See [state behavior and recovery](UPDATE_STATE.md).
Transport backoff, approved identification, and live validation remain unfinished;
unattended scheduling is not ready.

Dynu uses [its documented HTTPS protocol](https://www.dynu.com/en-US/DynamicDNS/IP-Update-Protocol)
with Basic authentication and the existing username/password/hostname keys.
`myipv6=no` prevents changes to IPv6 records. Exact good/nochg codes are accepted;
if an IPv4 detail is present, it must match the request. Unexpected details or
rejection codes fail. Persistent controls now enforce a ten-minute 911 suspension.
servererror/dnserr also receive a ten-minute conservative client delay; the provider
does not specify their interval. Other unconfirmed/HTTP responses persist a stop
requiring review. Normal CLI updates require state options, and controls cover all
Dynu sections/accounts in the same file, checked before discovery. No immediate
retry loop or native scheduling occurs. See [state behavior](UPDATE_STATE.md);
transport backoff and controlled live validation remain incomplete.

## ChangeIP and Securepoint: limited response evidence

ChangeIP's [official request guide](https://www.changeip.com/accounts/index.php?rp=/knowledgebase/34/DDNS-API-Information.html)
confirms HTTPS, Basic authentication, hostname, and myip. It does not document
response-body syntax. Our parser conservatively recognizes only the known first
line `200 Successful Update`, optionally followed by `(Address Used: IPv4)`;
an included address must match the requested one. Later diagnostic lines are
ignored. This heading appears in [DrayTek's manufacturer manual](https://draytek.com/download_de/Firmwares-Router/Vigor2962/DrayTek_UG_Vigor2962_V1.61.pdf),
an integration example rather than a current ChangeIP response specification.
Unknown/HTML bodies fail. Controlled live confirmation or a provider response
specification is needed before claiming complete service compatibility.

Securepoint's indexed official wiki identifies `https://update.spdyn.de/nic/update`
and good/nochg status codes, replacing the prototype's unrelated securepoint.de
URL. The full pages were blocked by the wiki's access check during this review.
See [host usage](https://wiki.securepoint.de/SPDyn/Hostverwenden) and
[return codes](https://wiki.securepoint.de/SPDyn/R%C3%BCckgabecodes).
The conservative parser accepts only a single good/nochg token with an optional
matching IPv4. This is an offline-tested policy, not a verified complete response
contract. Existing username/password/hostname keys remain unchanged; configure
credentials appropriate for the host in your Securepoint account. The SpDYN class now reuses this implementation, preserving its class name and
username/password/hostname configuration. Both retain these evidence limitations.

## YDNS

The [official API-v1 documentation](https://ydns.io/api/v1/) specifies a GET to
`https://ydns.io/api/v1/update/` with `host` and optional `ip`, using HTTP Basic
authentication. HTTP 200 plus the exact body good indicates acceptance. Errors
include 400, 401, and 404. The adapter now follows that contract and the shared
HTTP checks. It does not send the old undocumented domain/apikey query fields.
Use the API username/password from your account and a hostname, not a domain ID.
Legacy aliases and migration details are in [CLI.md](CLI.md). Optional record_id
selection and IPv6 updating are outside the current implementation.

## GoDaddy and retired Google Domains

GoDaddy's [v1 named-record replacement reference](https://developer.godaddy.com/en/docs/references/rest/domains/v1/record-replace-type-name)
scopes PUT to domain/type/name. This implementation uses type A and an explicit
hostname, replacing that named set with one IPv4 and TTL 600. It does not replace
all A records across the domain. The reference's prose says 204 No Content while
its response table lists 200; both are accepted only with an empty body. A readback
or propagation check is not implemented, so this is request acceptance only.

[Authentication documentation](https://developer.godaddy.com/en/docs/api-users/auth)
still lists classic sso-key credentials for Domains v1/v2, deprecated through
2026. The existing api_key/api_secret settings are retained; PAT/v3 migration is
future work. Use credentials for the correct account/environment. No live access
or API entitlement has been validated for this project.

[Squarespace's migration guide](https://support.squarespace.com/hc/en-us/articles/17131164996365-About-the-Google-Domains-migration-to-Squarespace)
says DDNS is unavailable for migrated Google Domains. GoogleDomains is therefore
retained as a disabled class with explicit configuration/direct-call errors before
network access. Existing static records and registrar settings are not changed.
DNSMax is also disabled following its confirmed closure, as documented below.

## FreeDNS.afraid.org (Afraid and FreeDNS)

Both class names now use the same API-v1 direct-key adapter. The
[provider router guide](https://freedns.afraid.org/guide/dd-wrt/) identifies the
update key as the portion after `?` in the Direct URL. The
[dynamic DNS help](https://freedns.afraid.org/faq/help.php?help_id=1) documents the
`address` override. Configure `api_key` with that key alone and `hostname` with
its associated A-record name. Afraid's old username/password configuration must
be migrated; FreeDNS's old Bearer authentication has been removed. No account
password is sent. Full URLs, query options, whitespace and control characters are
rejected as keys. This adapter does not implement v2 sync URLs.

The provider's public pages do not specify a full response grammar. Our
conservative offline parser accepts a single Updated line containing the exact
configured hostname and requested IP (optionally a host count), or the exact
`ERROR: Address IPv4 has not changed.` notice with the requested address.
This policy is informed by [ddclient's integration implementation](https://github.com/ddclient/ddclient/blob/main/ddclient.in)
and [IPFire's original v1 integration](https://lists.ipfire.org/ddns/CAHoP%2BV-mkAxCEntnh%3DCV3opBtVYFExLm8h%3D1atyL4EaNE79OoA%40mail.gmail.com/),
not a verified provider response specification. Unknown or multi-line bodies fail;
controlled live confirmation remains necessary.

The [provider FAQ](https://freedns.afraid.org/faq/) says linked updates are enabled
by default: records sharing the old destination IP can change together. Disable
linked updates in the provider's Dynamic DNS page when updates must be isolated.
A hostname in this configuration does not override that account setting, and a
no-change notice does not independently identify a record. Keep the key paired
with the correct hostname. The guide also describes a short cache for repeated
updates; no retries or scheduler are added here.

## ClouDNS

The [provider Synology guide](https://www.cloudns.net/wiki/article/175/) specifies
`https://ipv4.cloudns.net/api/dynamicURL/?q=KEY&ip=IPv4`. The adapter now uses that
fixed endpoint with encoded query parameters and shared HTTP protections instead
of the placeholder api.cloudns.net/ddns/update URL and account Basic auth.
Its setting `api_key` is the record-specific q value, not an account password.
Configure the associated A-record hostname; the key selects the record, and the
response does not independently verify the configured hostname.

The [getting-started guide](https://www.cloudns.net/wiki/article/364/) documents
OK when no response=json parameter is provided. The adapter accepts only exact
OK after outer whitespace is stripped. Optional JSON detail, IPv6, notification,
and failover-main-IP updates are not requested. Live acceptance and propagation
remain untested. See [CLI.md](CLI.md) for configuration migration.

## DNSMax closure

The [official DNSMax site](https://www.dnsmax.com/) announces January 27, 2026 as
the final day of operations, following its earlier DNSMax/ThatIP shutdown notice.
The adapter is retained but disabled for direct calls and CLI configuration, before
IP discovery or any update request. Its old api.dnsmas.net placeholder is removed.
This is a retired service, not an active adapter awaiting repair. No zone export,
registrar change, or migration to another DNS provider is performed by this tool.

## EntryDNS: limited response evidence

The [official REST instructions](https://entrydns.net/help/restapi) document HTTPS
GET to `https://entrydns.net/records/modify/TOKEN?ip=IPv4`. This replaces the old
placeholder api.entrydns.net URL and account Basic authentication. Configure a
record-specific token for an A record, plus its hostname. The token selects the
record; the response does not independently verify hostname or record type.
Tokens are encoded as one path component; dot-segment tokens are rejected.
Certificate verification remains enabled even though the provider's curl example
uses the insecure -k option. The implementation does not send PUT or JSON.

Public EntryDNS help does not specify response bodies. Our conservative exact
OK policy is informed by the [Asuswrt-Merlin integration example](https://github.com/RMerl/asuswrt-merlin.ng/wiki/DDNS-Sample-Scripts),
not a verified complete provider response contract. Unknown bodies fail. Controlled
live confirmation or a provider response specification remains necessary.

## EuroDynDNS

The [official documentation](https://www.eurodns.com/dynamic-dns-documentation)
specifies HTTPS at `https://update.eurodyndns.org/update/`, hostname/myip query
parameters, and Basic authentication. Existing username/password/hostname keys
are retained. The parser accepts a single good/nochg status; an optional IPv4
must match the request. Optional IP detail is a conservative compatibility policy,
not explicitly specified on the provider page. Rejection and unknown bodies fail.

EuroDNS says the service requires its nameservers and activated dynamic hosts,
and does not support round-robin records. Repeated unchanged updates can return
abuse. Opt-in persistent change detection can avoid recently accepted unchanged updates.
Account-wide stop/error state remains unfinished, so repeated failures or sections
can still send requests. Unattended scheduling remains blocked; no live DNS update
or propagation check has been performed.

### Securepoint/SpDYN error-control update

Normal CLI updates for both adapter names require state options. Rejected HTTP
responses or unconfirmed bodies persist a shared provider-wide stop checked before
IP discovery, so switching adapter names cannot bypass it. The official return-code
page remains access-blocked; retry timing was not verified and no automatic cooldown
is inferred. Stops require investigation and explicit clearing. This conservative
client behavior does not establish live interoperability or complete provider-policy
compliance. See [state behavior and recovery](UPDATE_STATE.md).
