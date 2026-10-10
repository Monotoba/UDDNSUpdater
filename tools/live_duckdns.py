"""Opt-in DuckDNS live integration check; never part of ordinary CI."""
import contextlib
import io
import ipaddress
from functools import lru_cache
import json
import os
from pathlib import Path
import re
import signal
import sys
import tempfile
import time
from urllib.parse import urlsplit

# Permit invocation as a script from the source checkout.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ddns_updater as app
from providers.provider_duckddns import DuckDNS
import requests


class LiveTestError(RuntimeError):
    pass


class LiveInterrupted(BaseException):
    """Keep interruption from being swallowed by DNS retry handlers."""


@lru_cache(maxsize=1)
def authoritative_servers():
    import dns.resolver
    resolver = dns.resolver.Resolver()
    resolver.lifetime = 10
    names = resolver.resolve('duckdns.org', 'NS')
    addresses = []
    for server in list(names)[:2]:
        try:
            addresses.append(resolver.resolve(str(server.target), 'A')[0].address)
        except Exception:
            continue
    if not addresses:
        raise LiveTestError('No authoritative DNS server available.')
    return tuple(addresses)


def authoritative_lookup(hostname):
    # Optional dependency is installed for live checks and DNS fixture tests.
    import dns.flags
    import dns.message
    import dns.query
    import dns.rcode
    import dns.rdatatype
    for address in authoritative_servers():
        try:
            query = dns.message.make_query(hostname, 'A')
            query.flags &= ~dns.flags.RD
            response = dns.query.udp(query, address, timeout=5)
            if response.flags & dns.flags.TC:
                response = dns.query.tcp(query, address, timeout=5)
            if not response.flags & dns.flags.AA or response.rcode() != dns.rcode.NOERROR:
                continue
            if any(rr.rdtype == dns.rdatatype.CNAME for rr in response.answer):
                continue
            values = [item.address for rr in response.answer
                      if rr.rdtype == dns.rdatatype.A and str(rr.name).rstrip('.') == hostname
                      for item in rr]
            if len(values) == 1:
                return str(ipaddress.IPv4Address(values[0]))
        except Exception:
            continue
    raise LiveTestError('Authoritative DNS did not confirm one A record.')


def wait_for_address(lookup, address, sleep=time.sleep, attempts=12):
    for attempt in range(attempts):
        try:
            if lookup() == address:
                return
        except Exception:
            pass
        if attempt + 1 < attempts:
            sleep(5)
    raise LiveTestError('Authoritative DNS verification timed out.')


def run_checks(lookup, update, restore, sleep=time.sleep):
    """Run injectable checks and restore after every attempted update."""
    baseline = str(ipaddress.IPv4Address(lookup()))
    print('Authoritative baseline established; original IPv4:', baseline, flush=True)
    try:
        address, count = update()
        address = str(ipaddress.IPv4Address(address))
        if count != 1:
            raise LiveTestError('First run did not make exactly one update request.')
        wait_for_address(lookup, address, sleep)
        repeated_address, count = update()
        if repeated_address != address or count != 0:
            raise LiveTestError('Repeat run did not suppress the unchanged update.')
        print('Live update, authoritative DNS, and repeat suppression passed.', flush=True)
    finally:
        # A failed request can still have changed DNS, so restore even on failure.
        if restore(baseline) is not True:
            raise LiveTestError('Restoration was not accepted; inspect the test record.')
        wait_for_address(lookup, baseline, sleep)
        print('Original A record restored and authoritatively verified.', flush=True)


def main():
    subdomain = os.environ.get('DUCKDNS_TEST_SUBDOMAIN', '')
    token = os.environ.get('DUCKDNS_TEST_TOKEN', '')
    if (not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', subdomain)
            or not re.fullmatch(r'[A-Za-z0-9-]{1,128}', token)):
        print('Configure a valid test subdomain and secret token.', file=sys.stderr)
        return 1
    hostname = subdomain + '.duckdns.org'
    original_request = requests.sessions.Session.request
    calls = []
    def track(session, method, url, *args, **kwargs):
        if urlsplit(url).netloc == 'www.duckdns.org':
            calls.append(True)
        return original_request(session, method, url, *args, **kwargs)
    def interrupted(*args):
        raise LiveInterrupted()
    old_handlers = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        old_handlers[sig] = signal.signal(sig, interrupted)
    requests.sessions.Session.request = track
    try:
        with tempfile.TemporaryDirectory(prefix='uddns-live-') as directory:
            root = Path(directory).resolve()
            if os.name == 'posix':
                os.chmod(root, 0o700)
            config = root/'config.ini'
            config.write_text(f'[live]\nddns_provider=DuckDNS\nsubdomain={subdomain}\ntoken={token}\n', encoding='utf-8')
            if os.name == 'posix':
                os.chmod(config, 0o600)
            state = root/'state.json'
            args = ['--config-file', str(config), '--no-log', '--state-file', str(state),
                    '--refresh-seconds', '3600']
            def update():
                calls.clear()
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    result = app.main(args)
                if result != 0:
                    raise LiveTestError('Live updater did not confirm success.')
                entries = json.loads(state.read_text(encoding='utf-8'))['entries']
                if len(entries) != 1:
                    raise LiveTestError('Live updater did not save one acceptance entry.')
                return next(iter(entries.values()))['ipv4'], len(calls)
            def restore(address):
                provider = object.__new__(DuckDNS)
                provider.name = 'live-restore'
                provider.config = {'subdomain': subdomain, 'token': token}
                provider.external_ip = address
                return provider.update_ddns()
            run_checks(lambda: authoritative_lookup(hostname), update, restore)
        return 0
    except (Exception, LiveInterrupted):
        # Never print exceptions: URLs or provider output may contain the token.
        print('Live DuckDNS check failed. Review phase messages; verify the record and restore the logged baseline if needed.', file=sys.stderr)
        return 1
    finally:
        requests.sessions.Session.request = original_request
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)


if __name__ == '__main__':
    raise SystemExit(main())
