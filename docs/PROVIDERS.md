# Provider repair status

Reviewed on 2026-10-08. All validation below is offline with mocked HTTP. No
live updates or DNS propagation checks have been performed. No release is available.

| Component | Implemented checks | Outstanding work |
| --- | --- | --- |
| Shared IPv4 discovery | HTTPS ipify IPv4 endpoint; strict IPv4 parsing; HTTP 200 required; redirects disabled; connect/read timeouts | Controlled live check |
| NamecheapDDNS | Encoded parameters; same HTTP rules; XML structure, zero error count, Done=true, matching IP, no error entries; rejects malformed/duplicate required fields and DOCTYPE | Controlled live response/propagation validation |
| DuckDNS | Encoded domains/token/IP; same HTTP rules; exact OK response without verbose mode | Controlled live acceptance/propagation validation |
| NoIP | HTTPS Basic authentication; encoded hostname/IP; client-identifying User-Agent; good/nochg plus matching IPv4 for each hostname | Approved client identification, change detection, persistent error/cooldown controls, controlled live validation |
| Dynu | HTTPS Basic authentication; encoded hostname/IP; myipv6=no; exact good/nochg status with matching IP when supplied | Persistent error/cooldown controls, controlled live validation |
| ChangeIP | HTTPS Basic auth; encoded parameters; known plain-text success heading, matching IP when present | Provider response documentation/controlled live confirmation |
| SecurePoint | Corrected HTTPS endpoint; Basic auth; encoded parameters; exact good/nochg with matching IP when present | Full wiki access/controlled live confirmation |
| SpDYN | Reuses the repaired SecurePoint implementation with its legacy class name/settings | Same wiki-access/live-validation limitations as SecurePoint |
| YDNS | Documented trailing-slash HTTPS endpoint; host/IP parameters; Basic auth; exact good response; corrected credential settings with legacy aliases | Controlled live validation; optional record_id selection not implemented |
| GoDaddyDDNS | Scoped v1 PUT by domain/type/name; explicit hostname; encoded paths; key/secret auth; shared HTTP protections; empty 200/204 acceptance | Controlled live validation; PAT/v3 migration; named multi-value A sets are replaced |
| GoogleDomains | Disabled before network access; retained discoverable class and migration error | Service unavailable for migrated domains |
| Afraid / FreeDNS | Shared API-v1 direct update key; encoded address; shared HTTP protections; conservative hostname/IP response checks | Controlled live response confirmation; account linked-update scope; v2 not implemented |
| Other 4 adapters | Configuration requirements and shared IPv4 discovery only | Audit current official endpoints/authentication and repair request/response contracts |

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

For shared discovery and the eleven repaired update adapters, connect/read timeouts
are 5/15 seconds, not a total wall-clock deadline. Redirects and non-200 statuses
are rejected. Bodies are limited to 65,536 characters **before parsing**, after
Requests has downloaded them; this is not a streaming/download memory limit.
Responses are closed after use, and exceptions omit raw request URLs and bodies.
There are no retries, IPv6 updates, cache, or propagation checks.

The unrepaired adapters are CloudNS, DNSMax, EntryDNS, and EuroDynDNS.
Their provider update calls still lack the shared timeout/redirect/encoding and
response checks. Some endpoints are explicit placeholders in the existing source.
Do not infer supported services from class names or HTTP success alone.

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
See [response requirements](https://www.noip.com/integrate/response). This prototype
makes no automatic retries, but currently has no persistent change cache, cooldown,
or account-wide stop state. Multiple sections or later invocations can still make
additional requests. Those are blockers for unattended use; do not schedule it.

Dynu uses [its documented HTTPS protocol](https://www.dynu.com/en-US/DynamicDNS/IP-Update-Protocol)
with Basic authentication and the existing username/password/hostname keys.
`myipv6=no` prevents changes to IPv6 records. Exact good/nochg codes are accepted;
if an IPv4 detail is present, it must match the request. Unexpected details or
rejection codes fail. Its 911 response requires a ten-minute suspension; that
persistent cooldown is not implemented. No retries or automatic scheduling occur.

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
The four unaudited adapters listed above are distinct from this retired service.

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
