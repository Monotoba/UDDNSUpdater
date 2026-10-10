import sys
import pytest
from tools import live_systemd as native


@pytest.mark.parametrize('phase', [None, 'partial', 'observe'])
def test_all_units_and_enablement_links_removed_after_failure(phase):
    state = {'unrelated.service': ('file', b'unrelated')}
    keys = ['probe.service', 'probe.timer', 'timers.target.wants/probe.timer']
    def install():
        state[keys[0]] = ('file', b'service')
        if phase == 'partial':
            raise RuntimeError('partial registration')
        state[keys[1]] = ('file', b'timer')
        state[keys[2]] = ('link', '../probe.timer')
    def observe():
        if phase == 'observe':
            raise RuntimeError('execution failed')
    def remove():
        for key in keys:
            state.pop(key, None)
    def run():
        native.exercise_units(lambda: dict(state), keys, install, observe, remove)
    if phase:
        with pytest.raises(RuntimeError):
            run()
    else:
        run()
    assert state == {'unrelated.service': ('file', b'unrelated')}


def test_collision_never_installed_or_removed():
    def forbidden():
        pytest.fail('Existing unit must not be changed')
    with pytest.raises(native.NativeCheckError):
        native.exercise_units(lambda: {'probe.service': b'original'}, ['probe.service'],
                              forbidden, forbidden, forbidden)


def test_inventory_detects_file_and_link_changes(tmp_path):
    path = tmp_path / 'unrelated.service'
    path.write_bytes(b'original')
    original = native.inventory(tmp_path)
    path.write_bytes(b'changed')
    assert native.inventory(tmp_path) != original
    if sys.platform != 'win32':
        link = tmp_path / 'timers.target.wants'
        link.mkdir()
        (link / 'unrelated.timer').symlink_to('../unrelated.timer')
        assert native.inventory(tmp_path)['timers.target.wants/unrelated.timer'] == ('link', '../unrelated.timer')


def test_non_hosted_runner_refused(monkeypatch):
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    assert native.main() == 1
