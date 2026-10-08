from pathlib import Path
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from UTaskScheduler import scheduler as legacy
from UTaskScheduler import utask_scheduler as app

ROOT = Path(__file__).resolve().parents[1]
SECRET = 'private%&value'
COMMAND = ['/path with spaces/python', '/script.py', '--value', SECRET, '']


@pytest.fixture(autouse=True)
def prohibit_system_mutations(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail('Native system task mutation prohibited')
    monkeypatch.setattr(subprocess, 'run', blocked)
    monkeypatch.setattr(os, 'system', blocked)
    monkeypatch.setattr(app, 'sys', SimpleNamespace(platform='linux', stderr=sys.stderr))


def write_config(tmp_path, content='[SCHEDULE]\nHour=*/6\nMinute=*/15\n'):
    path = tmp_path/'schedule.ini'
    path.write_text(content, encoding='utf-8')
    return path


@pytest.mark.parametrize('field,limit,expected', [('*', 24, list(range(24))),
    ('*/6', 24, [0,6,12,18]), ('*/15', 60, [0,15,30,45]), ('*/60', 60, [0]),
    ('23', 24, [23]), ('00', 60, [0]), (' 5 ', 60, [5])])
def test_cron_fields(field, limit, expected):
    assert app.UTaskScheduler.parse_cron_field(field, limit) == expected


@pytest.mark.parametrize('field', ['', '*/0', '*/61', '*/-1', '*/1/2', '60', '-1',
    '1,2', '1-3', '*/1.5', '１２', SECRET, '1\n2', '9'*5000, None])
def test_invalid_cron_fields_raise_controlled_error(field):
    with pytest.raises(app.SchedulerError) as error:
        app.UTaskScheduler.parse_cron_field(field, 60)
    assert SECRET not in str(error.value)


@pytest.mark.parametrize('system', ['Linux', 'Windows', 'Darwin'])
def test_plan_preserves_arguments_and_daily_trigger_product(tmp_path, monkeypatch, system):
    tag = {'Linux': 'linux', 'Windows': 'win32', 'Darwin': 'darwin'}[system]
    monkeypatch.setattr(app, 'sys', SimpleNamespace(platform=tag, stderr=sys.stderr))
    path = write_config(tmp_path)
    tasks = app.UTaskScheduler(path).schedule(COMMAND, dry_run=True)
    assert len(tasks) == 16
    assert {(t['hour'],t['minute']) for t in tasks} == {(h,m) for h in [0,6,12,18] for m in [0,15,30,45]}
    assert all(t['platform'] == system and t['action'] == COMMAND for t in tasks)
    tasks[0]['action'].append('changed')
    assert tasks[1]['action'] == COMMAND
    assert COMMAND[-1] == ''
    assert list(tmp_path.iterdir()) == [path]


def test_defaults_are_midnight(tmp_path):
    tasks = app.UTaskScheduler(write_config(tmp_path, '[SCHEDULE]\n')).plan(COMMAND)
    assert [(t['hour'],t['minute']) for t in tasks] == [(0,0)]


@pytest.mark.parametrize('content', ['', '[Task1]\nname=private', 'broken '+SECRET,
    '[SCHEDULE]\nHour=1\nHour=2', '[SCHEDULE]\nMinute=*/0',
    '[SCHEDULE]\nMinute=60', '[SCHEDULE]\nHour=24', '[SCHEDULE]\nYear=2026',
    '[SCHEDULE]\nHour=0\n[Task1]\naction=private'])
def test_configuration_rejected_without_writes(tmp_path, content):
    path = write_config(tmp_path, content)
    with pytest.raises(app.SchedulerError) as error:
        app.UTaskScheduler(path).plan(COMMAND)
    assert SECRET not in str(error.value)
    assert list(tmp_path.iterdir()) == [path]


def test_missing_and_non_utf8_config_are_sanitized(tmp_path):
    path = tmp_path/SECRET
    with pytest.raises(app.SchedulerError) as error:
        app.UTaskScheduler(path).plan(COMMAND)
    assert SECRET not in str(error.value)
    path.write_bytes(b'\xffprivate')
    with pytest.raises(app.SchedulerError):
        app.UTaskScheduler(path).plan(COMMAND)


@pytest.mark.parametrize('command', ['', 'python script.py', [], [''], [' '], [1],
    ['python', None], ['python', 'bad\nargument'], ['python', 'bad\x00argument']])
def test_argument_list_validation(tmp_path, command):
    with pytest.raises(app.SchedulerError):
        app.UTaskScheduler(write_config(tmp_path)).plan(command)


@pytest.mark.parametrize('hour,minute', [(24,0), (-1,0), (0,60), (0,-1), (True,0), ('0',0)])
def test_invalid_direct_trigger(hour, minute):
    with pytest.raises(app.SchedulerError):
        app.UTaskScheduler().schedule_task(COMMAND, hour, minute, dry_run=True)


def test_unsupported_platform(tmp_path, monkeypatch):
    monkeypatch.setattr(app, 'sys', SimpleNamespace(platform='unknown', stderr=sys.stderr))
    with pytest.raises(app.SchedulerError, match='Unsupported'):
        app.UTaskScheduler(write_config(tmp_path)).plan(COMMAND)


def test_native_installation_explicitly_blocked(tmp_path):
    scheduler = app.UTaskScheduler(write_config(tmp_path))
    with pytest.raises(app.SchedulerUnavailableError):
        scheduler.schedule(COMMAND)
    with pytest.raises(app.SchedulerUnavailableError):
        scheduler.schedule_task(COMMAND, 0, 0)


@pytest.mark.parametrize('dry,valid,expected', [(True,True,0), (True,False,2), (False,True,1), (False,False,2)])
def test_cli_status_no_command_disclosure_or_writes(tmp_path, capsys, dry, valid, expected):
    path = write_config(tmp_path, '[SCHEDULE]\nHour=0\nMinute='+('15' if valid else SECRET))
    args = ['--config-file', str(path)] + (['--dry-run'] if dry else []) + ['--', *COMMAND]
    assert app.main(args) == expected
    output = capsys.readouterr()
    assert SECRET not in output.out+output.err
    if expected == 0:
        assert 'No tasks installed' in output.out
    assert list(tmp_path.iterdir()) == [path]


def test_legacy_module_uses_same_import():
    assert legacy.UTaskScheduler is app.UTaskScheduler


def test_child_module_and_script_work_outside_repository(tmp_path, monkeypatch):
    # Restore only the runner to start child Python; prohibit task tools in each child.
    monkeypatch.undo()
    path = write_config(tmp_path, '[SCHEDULE]\nHour=0\nMinute=15')
    hook = tmp_path/'sitecustomize.py'
    hook.write_text("import os, subprocess\ndef fail(*a, **k):\n    raise RuntimeError('Native mutation prohibited')\nos.system=fail\nsubprocess.run=fail\n")
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join([str(tmp_path), str(ROOT)])
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    for entry in [['-m','UTaskScheduler.utask_scheduler'], [str(ROOT/'UTaskScheduler/utask_scheduler.py')]]:
        result = subprocess.run([sys.executable, *entry, '--config-file', str(path), '--dry-run', '--', *COMMAND],
            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stderr
        assert 'No tasks installed' in result.stdout
        assert SECRET not in result.stdout+result.stderr
    assert set(p.name for p in tmp_path.iterdir()) == {'schedule.ini','sitecustomize.py'}
