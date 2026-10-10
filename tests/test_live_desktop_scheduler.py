from datetime import datetime, timezone
import json
import sys
import pytest
from tools import live_desktop_scheduler as native


@pytest.mark.parametrize('failure', [None, 'install', 'observe'])
def test_lifecycle_removes_partial_probe_preserves_unrelated(failure):
    state = {'unrelated': 'definition'}
    def install():
        state['probe'] = 'temporary'
        if failure == 'install':
            raise RuntimeError('partial registration')
    def observe():
        if failure == 'observe':
            raise RuntimeError('execution failed')
    def run():
        native.exercise(lambda: dict(state), 'probe', install, observe, lambda: state.pop('probe'))
    if failure:
        with pytest.raises(RuntimeError):
            run()
    else:
        run()
    assert state == {'unrelated': 'definition'}


def test_collision_never_mutates():
    def forbidden():
        pytest.fail('Must not mutate a colliding task')
    with pytest.raises(native.NativeCheckError, match='already exists'):
        native.exercise(lambda: {'probe': 'existing'}, 'probe', forbidden, forbidden, forbidden)


def test_failed_cleanup_is_reported():
    state = {}
    with pytest.raises(native.NativeCheckError, match='cleanup'):
        native.exercise(lambda: dict(state), 'probe', lambda: state.update(probe='definition'),
                        lambda: None, lambda: None)


def test_changed_unrelated_definition_is_reported():
    state = {'unrelated': 'before'}
    def install():
        state.update(probe='definition', unrelated='changed')
    with pytest.raises(native.NativeCheckError):
        native.exercise(lambda: dict(state), 'probe', install, lambda: None, lambda: state.pop('probe'))
    assert 'probe' not in state


def test_scheduled_record_validation(tmp_path):
    started = datetime(2026, 1, 1, tzinfo=timezone.utc)
    record = {'schema_version': 1, 'arguments': native.ARGUMENTS, 'executable': sys.executable,
              'timestamp_utc': '2026-01-01T00:01:00+00:00', 'working_directory': str(tmp_path)}
    native.verify_record(record, sys.executable, started)
    for key, value in [('arguments', ['wrong']), ('timestamp_utc', '2025-01-01T00:00:00+00:00'),
                       ('timestamp_utc', '2026-01-01T00:01:00'), ('working_directory', 'relative')]:
        with pytest.raises(native.NativeCheckError):
            native.verify_record(dict(record, **{key: value}), sys.executable, started)


def test_observation_retries_partial_record(tmp_path):
    path = tmp_path / 'uddns-probe-test.json'
    path.write_text('')
    ticks = iter([0, 1, 2])
    def finish_write(seconds):
        path.write_text(json.dumps({'schema_version': 1, 'arguments': native.ARGUMENTS,
                        'executable': sys.executable, 'working_directory': str(tmp_path),
                        'timestamp_utc': '2026-01-01T00:01:00+00:00'}))
    native.observe(tmp_path, sys.executable, datetime(2026, 1, 1, tzinfo=timezone.utc),
                   clock=lambda: next(ticks), sleep=finish_write)


def test_no_execution_times_out(tmp_path):
    ticks = iter([0, 181])
    with pytest.raises(native.NativeCheckError, match='No scheduled execution'):
        native.observe(tmp_path, sys.executable, datetime.now(timezone.utc),
                       clock=lambda: next(ticks), sleep=lambda seconds: None)


def test_non_hosted_runner_refused(monkeypatch, capsys):
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    assert native.main() == 1
    assert 'disposable GitHub-hosted' in capsys.readouterr().err
