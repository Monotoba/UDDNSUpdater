# Provider repair status

Reviewed on 2026-10-08. All validation below is offline with mocked HTTP. No
live updates or DNS propagation checks have been performed. No release is available.

| Component | Implemented checks | Outstanding work |
| --- | --- | --- |
| Shared IPv4 discovery | HTTPS ipify IPv4 endpoint; strict IPv4 parsing; HTTP 200 required; redirects disabled; connect/read timeouts | Controlled live check |
| NamecheapDDNS | Encoded parameters; same HTTP rules; XML structure, zero error count, Done=true, matching IP, no error entries; rejects malformed/duplicate required fields and DOCTYPE | Controlled live response/propagation validation |
| DuckDNS | Encoded domains/token/IP; same HTTP rules; exact OK response without verbose mode | Controlled live acceptance/propagation validation |
| Other 14 adapters | Configuration requirements and shared IPv4 discovery only | Audit current official endpoints/authentication and repair request/response contracts |

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

For shared discovery and the two repaired update adapters, connect/read timeouts
are 5/15 seconds, not a total wall-clock deadline. Redirects and non-200 statuses
are rejected. Bodies are limited to 65,536 characters **before parsing**, after
Requests has downloaded them; this is not a streaming/download memory limit.
Responses are closed after use, and exceptions omit raw request URLs and bodies.
There are no retries, IPv6 updates, cache, or propagation checks.

The unrepaired adapters are Afraid, ChangeIP, CloudNS, DNSMax, Dynu, EntryDNS,
EuroDynDNS, FreeDNS, GoDaddyDDNS, GoogleDomains, NoIP, SecurePoint, SpDYN, and YDNS.
Their provider update calls still lack the shared timeout/redirect/encoding and
response checks. Some endpoints are explicit placeholders in the existing source.
Do not infer supported services from class names or HTTP success alone.
