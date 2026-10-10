# Controlled DuckDNS live check

Run date (UTC): 2026-10-10T03:04:32.073735+00:00
Candidate: local ae19054; provider code matches main f6841ce95a32dd70241d7eef5fca8828951c15bc.
Platform: Linux; Python 3.12. User authorized a disposable DuckDNS hostname.
No credentials or address values are included in this record.

| Check | Result |
| --- | --- |
| Baseline | Recursive DNS returned one existing A address |
| Actual CLI update | Exit 0; one IP-discovery request and one DuckDNS update request |
| Persistent acceptance | One acceptance entry, zero error controls |
| Immediate repeat | Exit 0; one discovery request, zero DuckDNS update requests |
| Recursive DNS after update | Returned exactly the IPv4 accepted by the updater |
| Authoritative DNS | Not verified: direct queries to two authoritative servers failed with OSError in this execution environment |
| Restoration | DuckDNS adapter accepted restoration to the original A address; recursive DNS returned that address |
| Cleanup | Temporary configuration and state removed; no task installed |

The execution used the existing adapter, real HTTPS endpoints, valid TLS checks,
and a protected temporary configuration/state directory. HTTP instrumentation
counted destination hosts only. The restoration used the adapter's update method
with the baseline address explicitly supplied, without public-IP rediscovery.

This confirms one DuckDNS IPv4 update, recursive visibility, repeat suppression,
and restoration for this candidate/account. It does not establish authoritative
propagation, scheduled execution, live error recovery, other accounts/providers,
or general production readiness. The user should regenerate the exposed test
token and remove the disposable hostname when finished.

## Subsequent GitHub Actions validation

[Live workflow run 38022228218](https://github.com/Monotoba/UDDNSUpdater/actions/runs/38022228218)
passed on main commit 5d8e6ea89558734fb163c184a5ba0fa3e0710a29.
At 2026-10-10 03:55 UTC it established an authoritative baseline, confirmed the
updated authoritative A record, verified repeat suppression, restored the
original address, and authoritatively verified restoration. This closes the
authoritative-query gap for this DuckDNS candidate/account on the hosted runner.
Other providers and native scheduler execution are separate validation gates.
The dedicated hostname is retained for manual live workflow checks.
