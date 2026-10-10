import pytest
import requests
from tools import live_duckdns as live

BASELINE = '192.0.2.1'
UPDATED = '198.51.100.2'


@pytest.fixture(autouse=True)
def no_http(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail('Live HTTP forbidden in offline tests')
    monkeypatch.setattr(requests.sessions.Session, 'request', blocked)


def scenario():
    current = {'address': BASELINE}
    calls = []
    def lookup():
        return current['address']
    def update():
        calls.append('update')
        current['address'] = UPDATED
        return UPDATED, 1 if calls.count('update') == 1 else 0
    def restore(address):
        calls.append(('restore', address))
        current['address'] = address
        return True
    return lookup, update, restore, calls, current


def test_live_sequence_restores_and_checks_repeat(capsys):
    lookup, update, restore, calls, current = scenario()
    live.run_checks(lookup, update, restore, sleep=lambda _: None)
    assert calls == ['update', 'update', ('restore', BASELINE)]
    assert current['address'] == BASELINE
    assert 'authoritatively verified' in capsys.readouterr().out


@pytest.mark.parametrize('failure', ['request', 'first-count', 'propagation', 'repeat-count', 'interrupt'])
def test_every_attempted_update_is_restored(failure):
    lookup, normal_update, restore, calls, current = scenario()
    def update():
        address, count = normal_update()
        if failure == 'request':
            raise RuntimeError('sensitive token')
        if failure == 'interrupt':
            raise KeyboardInterrupt()
        if failure == 'first-count':
            return address, 0
        if failure == 'propagation':
            current['address'] = BASELINE
        if failure == 'repeat-count' and count == 0:
            return address, 1
        return address, count
    with pytest.raises(BaseException):
        live.run_checks(lookup, update, restore, sleep=lambda _: None)
    assert calls[-1] == ('restore', BASELINE)
    assert current['address'] == BASELINE


def test_missing_authoritative_baseline_prevents_update():
    calls = []
    def lookup():
        raise live.LiveTestError('unavailable')
    with pytest.raises(live.LiveTestError):
        live.run_checks(lookup, lambda: calls.append('update'), lambda _: calls.append('restore'))
    assert calls == []


@pytest.mark.parametrize('accepted', [False, None])
def test_restoration_requires_explicit_acceptance(accepted):
    lookup, update, _, _, _ = scenario()
    with pytest.raises(live.LiveTestError, match='Restoration'):
        live.run_checks(lookup, update, lambda _: accepted, sleep=lambda _: None)


def test_restoration_dns_failure_fails_run():
    lookup, update, _, _, _ = scenario()
    with pytest.raises(live.LiveTestError, match='DNS verification'):
        live.run_checks(lookup, update, lambda _: True, sleep=lambda _: None)


def test_dns_poll_retries_boundedly():
    values = iter([None, BASELINE, UPDATED])
    sleeps = []
    live.wait_for_address(lambda: next(values), UPDATED, sleeps.append, attempts=3)
    assert sleeps == [5, 5]


def test_missing_secret_fails_without_network(monkeypatch, capsys):
    monkeypatch.setenv('DUCKDNS_TEST_SUBDOMAIN', 'monotoba-uddns-test')
    monkeypatch.delenv('DUCKDNS_TEST_TOKEN', raising=False)
    assert live.main() == 1
    assert 'secret token' in capsys.readouterr().err


def test_main_failure_does_not_print_secret(monkeypatch, capsys):
    secret = 'private-test-token'
    monkeypatch.setenv('DUCKDNS_TEST_SUBDOMAIN', 'monotoba-uddns-test')
    monkeypatch.setenv('DUCKDNS_TEST_TOKEN', secret)
    def fail(*args):
        raise RuntimeError(secret)
    monkeypatch.setattr(live, 'authoritative_lookup', fail)
    original = requests.sessions.Session.request
    assert live.main() == 1
    captured = capsys.readouterr()
    assert secret not in captured.out + captured.err
    assert requests.sessions.Session.request is original


@pytest.mark.parametrize('case', ['accepted', 'not-authoritative', 'wrong-name', 'cname', 'multiple', 'tcp'])
def test_authoritative_response_checks(monkeypatch, case):
    import dns.flags
    import dns.message
    import dns.rrset
    import dns.query
    hostname = 'test.duckdns.org'
    query = dns.message.make_query(hostname, 'A')
    response = dns.message.make_response(query)
    response.flags |= dns.flags.AA
    name = 'other.duckdns.org' if case == 'wrong-name' else hostname
    values = [BASELINE, UPDATED] if case == 'multiple' else [UPDATED]
    response.answer.append(dns.rrset.from_text(name, 60, 'IN', 'A', *values))
    if case == 'not-authoritative':
        response.flags &= ~dns.flags.AA
    if case == 'cname':
        response.answer.append(dns.rrset.from_text(hostname, 60, 'IN', 'CNAME', 'other.duckdns.org.'))
    monkeypatch.setattr(live, 'authoritative_servers', lambda: ('192.0.2.53',))
    calls = []
    def udp(question, address, timeout):
        assert not question.flags & dns.flags.RD
        assert timeout == 5
        calls.append('udp')
        if case == 'tcp':
            truncated = dns.message.make_response(question)
            truncated.flags |= dns.flags.TC
            return truncated
        return response
    def tcp(*args, **kwargs):
        calls.append('tcp')
        return response
    monkeypatch.setattr(dns.query, 'udp', udp)
    monkeypatch.setattr(dns.query, 'tcp', tcp)
    if case in ['accepted', 'tcp']:
        assert live.authoritative_lookup(hostname) == UPDATED
    else:
        with pytest.raises(live.LiveTestError):
            live.authoritative_lookup(hostname)
    assert calls == (['udp', 'tcp'] if case == 'tcp' else ['udp'])


def test_main_real_cli_with_fake_transport_restores(monkeypatch, capsys):
    from types import SimpleNamespace
    current = {'address': BASELINE}
    calls = []
    secret = 'offline-private-token'
    monkeypatch.setenv('DUCKDNS_TEST_SUBDOMAIN', 'test')
    monkeypatch.setenv('DUCKDNS_TEST_TOKEN', secret)
    monkeypatch.setattr(live, 'authoritative_lookup', lambda _: current['address'])
    def request(session, method, url, **kwargs):
        calls.append(url)
        if url == 'https://api.ipify.org':
            body = UPDATED
        else:
            assert kwargs['params']['token'] == secret
            current['address'] = kwargs['params']['ip']
            body = 'OK'
        return SimpleNamespace(status_code=200, text=body, close=lambda: None)
    monkeypatch.setattr(requests.sessions.Session, 'request', request)
    assert live.main() == 0
    assert calls.count('https://api.ipify.org') == 2
    assert calls.count('https://www.duckdns.org/update') == 2  # update + restore
    assert current['address'] == BASELINE
    captured = capsys.readouterr()
    assert secret not in captured.out + captured.err
    assert captured.err == ''


def test_interruption_escapes_dns_polling():
    def interrupted():
        raise live.LiveInterrupted()
    with pytest.raises(live.LiveInterrupted):
        live.wait_for_address(interrupted, UPDATED, sleep=lambda _: None)
