from pathlib import Path
import sys
import pytest
from tools import live_cron as native


@pytest.mark.parametrize('original', [None, ''])
def test_native_lifecycle_preserves_original(original):
    state = {'text': original}
    events = []
    def write(text):
        state['text'] = text
    def install():
        state['text'] += native.BEGIN + '\nmanaged entry\n'
    def uninstall():
        state['text'] = native.SENTINEL
    native.exercise(lambda: state['text'], write, lambda: write(None), install, uninstall,
                    lambda: events.append('scheduled run'))
    assert state['text'] == original
    assert events == ['scheduled run']


@pytest.mark.parametrize('phase', ['write', 'install', 'observe', 'uninstall', 'preservation'])
def test_failed_native_lifecycle_restores_original(phase):
    state = {'text': None}
    def fail():
        raise RuntimeError('partial native failure')
    def write(text):
        state['text'] = text
        if phase == 'write':
            fail()
    def install():
        state['text'] += native.BEGIN + '\n'
        if phase == 'install':
            fail()
    def uninstall():
        state['text'] = native.SENTINEL if phase != 'preservation' else 'unexpected'
        if phase == 'uninstall':
            fail()
    with pytest.raises((RuntimeError, native.NativeCheckError)):
        native.exercise(lambda: state['text'], write, lambda: state.update(text=None),
                        install, uninstall, fail if phase == 'observe' else lambda: None)
    assert state['text'] is None


def test_existing_crontab_is_never_changed():
    def forbidden(*args):
        pytest.fail('Must not mutate an existing nonempty crontab')
    with pytest.raises(native.NativeCheckError):
        native.exercise(lambda: 'existing task\n', forbidden, forbidden, forbidden, forbidden, forbidden)


def test_probe_context_validation(tmp_path):
    record = {'schema_version': 1, 'arguments': native.ARGUMENTS,
              'executable': sys.executable, 'working_directory': str(tmp_path),
              'timestamp_utc': '2026-10-10T04:00:00+00:00'}
    native.verify_record(record, sys.executable, tmp_path)
    for key, value in [('arguments', ['wrong']), ('working_directory', str(Path.cwd())),
                       ('timestamp_utc', '2026-10-10T04:00:00')]:
        with pytest.raises(native.NativeCheckError):
            native.verify_record(dict(record, **{key: value}), sys.executable, tmp_path)


def test_local_execution_refused(monkeypatch, capsys):
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    assert native.main() == 1
    assert 'disposable GitHub-hosted' in capsys.readouterr().err
