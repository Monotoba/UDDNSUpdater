import json
import os
import pytest
import update_state as state

KEY = 'a' * 64
IP = '192.0.2.1'


def test_round_trip_and_expiry(tmp_path):
    path = tmp_path / 'state.json'
    with state.open_state(path) as store:
        assert not store.matches(KEY, IP, now=100, max_age=10)
        store.record_accepted(KEY, IP, accepted_at=100)
        store.save()
    with state.open_state(path) as store:
        assert store.matches(KEY, IP, now=109, max_age=10)
        assert not store.matches(KEY, IP, now=110, max_age=10)
        assert not store.matches(KEY, IP, now=99, max_age=10)
        assert not store.matches(KEY, '192.0.2.2', now=100, max_age=10)
    assert json.loads(path.read_text()) == {'version': 1, 'entries': {KEY: {'ipv4': IP, 'accepted_at': 100}}}
    if os.name == 'posix':
        assert path.stat().st_mode & 0o777 == 0o600


def test_no_automatic_save(tmp_path):
    path = tmp_path / 'state.json'
    with state.open_state(path) as store:
        store.record_accepted(KEY, IP, accepted_at=100)
    assert not path.exists()
    assert not path.with_suffix('.json.lock').exists()


def test_concurrent_lock_preserves_owner(tmp_path):
    path = tmp_path / 'state.json'
    with state.open_state(path):
        with pytest.raises(state.StateError):
            with state.open_state(path):
                pytest.fail('second writer acquired lock')
        assert path.with_suffix('.json.lock').exists()
    assert not path.with_suffix('.json.lock').exists()


@pytest.mark.parametrize('content', ['secret', '{', '{}', '{"version":2,"entries":{}}',
    '{"version":true,"entries":{}}', '{"version":1,"version":1,"entries":{}}',
    '{"version":1,"entries":{"secret":{}}}',
    json.dumps({'version': 1, 'entries': {KEY: {'ipv4': '::1', 'accepted_at': 100}}}),
    json.dumps({'version': 1, 'entries': {KEY: {'ipv4': IP, 'accepted_at': True}}}),
    json.dumps({'version': 1, 'entries': {KEY: {'ipv4': IP, 'accepted_at': -1}}})])
def test_corrupt_fails_closed(tmp_path, content):
    path = tmp_path / 'state.json'
    path.write_text(content)
    with pytest.raises(state.StateError) as error:
        with state.open_state(path):
            pytest.fail('corrupt state accepted')
    assert 'secret' not in str(error.value)
    assert path.read_text() == content
    assert not path.with_suffix('.json.lock').exists()


def test_oversize(tmp_path):
    path = tmp_path / 'state.json'
    path.write_bytes(b'x' * (state.UpdateState.max_bytes + 1))
    with pytest.raises(state.StateError):
        with state.open_state(path):
            pass


def test_atomic_failure_preserves_old(tmp_path, monkeypatch):
    path = tmp_path / 'state.json'
    with state.open_state(path) as store:
        store.record_accepted(KEY, IP, accepted_at=100)
        store.save()
    old = path.read_bytes()
    def fail(*args):
        raise OSError('SECRET')
    with pytest.raises(state.StateError) as error:
        with state.open_state(path) as store:
            store.record_accepted(KEY, '192.0.2.2', accepted_at=200)
            monkeypatch.setattr(state.os, 'replace', fail)
            store.save()
    assert path.read_bytes() == old
    assert list(tmp_path.iterdir()) == [path]
    assert 'SECRET' not in str(error.value)


@pytest.mark.parametrize('key,address,when', [('bad', IP, 100), (KEY, '::1', 100),
    (KEY, 1, 100), (KEY, IP, True), (KEY, IP, -1), (KEY, IP, 1.5)])
def test_invalid_record(tmp_path, key, address, when):
    with state.open_state(tmp_path / 'state.json') as store:
        with pytest.raises(state.StateError):
            store.record_accepted(key, address, accepted_at=when)
        assert store.entries == {}


def test_max_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(state.UpdateState, 'max_entries', 1)
    with state.open_state(tmp_path / 'state.json') as store:
        store.record_accepted(KEY, IP, accepted_at=100)
        with pytest.raises(state.StateError):
            store.record_accepted('b' * 64, IP, accepted_at=100)
        store.record_accepted(KEY, IP, accepted_at=101)


def test_lock_released_after_caller_error(tmp_path):
    path = tmp_path / 'state.json'
    with pytest.raises(RuntimeError):
        with state.open_state(path):
            raise RuntimeError
    with state.open_state(path):
        pass


@pytest.mark.skipif(os.name != 'posix', reason='portable symlink creation needs POSIX')
def test_symlink_rejected(tmp_path):
    target = tmp_path / 'target'
    target.write_text('secret')
    path = tmp_path / 'state.json'
    path.symlink_to(target)
    with pytest.raises(state.StateError):
        with state.open_state(path):
            pass
    assert target.read_text() == 'secret'


@pytest.mark.parametrize('age', [0, -1, True, 1.5])
def test_invalid_age(tmp_path, age):
    with state.open_state(tmp_path / 'state.json') as store:
        with pytest.raises(state.StateError):
            store.matches(KEY, IP, now=100, max_age=age)


def test_save_rejects_invalid_mutation(tmp_path):
    path = tmp_path / 'state.json'
    with state.open_state(path) as store:
        store.entries['bad'] = {'ipv4': IP, 'accepted_at': 100}
        with pytest.raises(state.StateError):
            store.save()
    assert not path.exists()


def test_missing_parent(tmp_path):
    with pytest.raises(state.StateError):
        with state.open_state(tmp_path / 'missing' / 'state.json'):
            pass
