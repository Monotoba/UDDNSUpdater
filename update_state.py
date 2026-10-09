"""Local accepted-update state; no network activity or automatic update skipping."""
from contextlib import contextmanager
import ipaddress
import json
import os
from pathlib import Path
import re
import tempfile


class StateError(RuntimeError):
    """Controlled state-store failure without paths or stored values."""


def valid_key(key):
    return isinstance(key, str) and re.fullmatch(r'[0-9a-f]{64}', key) is not None


def ipv4(value):
    try:
        if not isinstance(value, str):
            raise ValueError
        return str(ipaddress.IPv4Address(value))
    except (ValueError, TypeError):
        raise StateError('Invalid state IPv4 address.') from None


def timestamp(value):
    if type(value) is not int or not 0 <= value <= 253402300799:
        raise StateError('Invalid state timestamp.')
    return value


class UpdateState:
    """Use through open_state(); callers explicitly save accepted updates."""
    max_bytes = 262144
    max_entries = 1000

    def __init__(self, path):
        self.path = Path(path)
        self.entries = {}

    def load(self):
        try:
            if self.path.is_symlink():
                raise StateError('State file must not be a symbolic link.')
            try:
                with self.path.open('rb') as handle:
                    raw = handle.read(self.max_bytes + 1)
            except FileNotFoundError:
                self.entries = {}
                return
            if len(raw) > self.max_bytes:
                raise StateError('State file exceeds size limit.')
            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError
                    result[key] = value
                return result
            data = json.loads(raw, object_pairs_hook=unique)
            if (not isinstance(data, dict) or set(data) != {'version', 'entries'}
                    or type(data['version']) is not int or data['version'] != 1
                    or not isinstance(data['entries'], dict) or len(data['entries']) > self.max_entries):
                raise ValueError
            entries = {}
            for key, record in data['entries'].items():
                if not valid_key(key) or not isinstance(record, dict) or set(record) != {'ipv4', 'accepted_at'}:
                    raise ValueError
                entries[key] = {'ipv4': ipv4(record['ipv4']), 'accepted_at': timestamp(record['accepted_at'])}
            self.entries = entries
        except StateError:
            raise
        except (OSError, ValueError, UnicodeError, RecursionError, TypeError):
            raise StateError('Cannot read valid update state.') from None

    def matches(self, key, address, *, now, max_age):
        if not valid_key(key):
            raise StateError('Invalid state service key.')
        address = ipv4(address)
        now = timestamp(now)
        if type(max_age) is not int or max_age <= 0:
            raise StateError('Invalid state maximum age.')
        record = self.entries.get(key)
        return bool(record and record['ipv4'] == address
                    and 0 <= now - record['accepted_at'] < max_age)

    def record_accepted(self, key, address, *, accepted_at):
        if not valid_key(key):
            raise StateError('Invalid state service key.')
        record = {'ipv4': ipv4(address), 'accepted_at': timestamp(accepted_at)}
        if key not in self.entries and len(self.entries) >= self.max_entries:
            raise StateError('State entry limit reached.')
        self.entries[key] = record

    def save(self):
        temporary = None
        try:
            if self.path.is_symlink():
                raise StateError('State file must not be a symbolic link.')
            if not isinstance(self.entries, dict) or len(self.entries) > self.max_entries:
                raise StateError('Invalid state entries.')
            for key, record in self.entries.items():
                if not valid_key(key) or not isinstance(record, dict) or set(record) != {'ipv4', 'accepted_at'}:
                    raise StateError('Invalid state record.')
                ipv4(record['ipv4'])
                timestamp(record['accepted_at'])
            payload = json.dumps({'version': 1, 'entries': self.entries}, sort_keys=True).encode('utf-8') + b'\n'
            if len(payload) > self.max_bytes:
                raise StateError('State file exceeds size limit.')
            with tempfile.NamedTemporaryFile(mode='wb', dir=self.path.parent, prefix='.uddns-state-', delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            temporary = None
        except StateError:
            raise
        except (OSError, ValueError, TypeError):
            raise StateError('Cannot save update state.') from None
        finally:
            if temporary is not None:
                try:
                    temporary.unlink()
                except OSError:
                    pass


@contextmanager
def open_state(path):
    """Hold an exclusive sidecar lock for the complete read/update/save cycle."""
    state = UpdateState(path)
    lock = state.path.with_name(state.path.name + '.lock')
    acquired = False
    try:
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            acquired = True
            os.close(descriptor)
        except OSError:
            raise StateError('Cannot acquire update-state lock.') from None
        state.load()
        yield state
    finally:
        if acquired:
            try:
                lock.unlink()
            except OSError:
                raise StateError('Cannot release update-state lock.') from None
