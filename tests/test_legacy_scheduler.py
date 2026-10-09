import os
import subprocess
from types import SimpleNamespace
import pytest
from UTaskScheduler import scheduler as legacy
from UTaskScheduler import utask_scheduler as app
from UTaskScheduler.utask_scheduler import SchedulerError


@pytest.fixture(autouse=True)
def no_native(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail('Native execution attempted')
    monkeypatch.setattr(os, 'system', blocked)
    monkeypatch.setattr(subprocess, 'run', blocked)
    monkeypatch.setattr(app, 'sys', SimpleNamespace(platform='linux', stderr=app.sys.stderr))


def write(tmp_path, content):
    path = tmp_path / 'tasks.ini'
    path.write_text(content, encoding='utf-8')
    return path


def test_arguments_and_complete_plan(tmp_path):
    path = write(tmp_path, '''[Task1]
name=First
action=["/path with spaces/python", "", "100%", "a\\\\b", "<tag>"]
hours=*/6
minutes=*/15
[Task2]
action=["/bin/echo", "literal"]
hours=23
minutes=59
''')
    tasks = legacy.parse_config(path)
    assert tasks[0]['action'] == ['/path with spaces/python', '', '100%', 'a\\b', '<tag>']
    plans = legacy.plan_tasks(path)
    assert len(plans) == 2 and len(plans[0]['triggers']) == 16
    assert [(t['hour'], t['minute']) for t in plans[0]['triggers']] == [(h, m) for h in range(0,24,6) for m in range(0,60,15)]
    assert plans[1]['triggers'][0]['hour'] == 23


@pytest.mark.parametrize('content', ['', '[SCHEDULE]\nhour=0', '[Task0]\naction=["python"]',
    '[TaskX]\naction=["python"]', '[DEFAULT]\nhours=0\n[Task1]\naction=["python"]',
    '[Task1]\naction=python job.py', '[Task1]\naction="python"', '[Task1]\naction=[]',
    '[Task1]\naction=[1]', '[Task1]\naction=["python", "\\u0000"]',
    '[Task1]\naction=["python"]\nunknown=SECRET',
    '[Task1]\naction=["python"]\nhours=24', '[Task1]\naction=["python"]\nminutes=60',
    '[Task1]\naction=["python"]\nname=', '[Task1]\naction=["python"]\ndate=2026-10-09',
    '[Task1]\naction=["python"]\ndays=1', '[Task1]\naction=["python"]\nweeks=*/2',
    '[Task1]\naction=["python"]\nmonths=1', '[Task1]\naction=["python"]\nyears=2026',
    '[Task1]\naction=["python"]\nname=Same\n[Task2]\naction=["python"]\nname=same',
    '[Task1]\naction=["python"]\n[Task1]\naction=["python"]'])
def test_invalid_configs(tmp_path, content):
    with pytest.raises(SchedulerError):
        legacy.parse_config(write(tmp_path, content))


def test_cli_and_blocked_default(tmp_path, capsys):
    path = write(tmp_path, '[Task1]\naction=["python", "SECRET"]\nhours=0\nminutes=0\n')
    assert legacy.main(['--config-file', str(path), '--dry-run']) == 0
    out = capsys.readouterr()
    assert out.out == 'Validated 1 task(s), 1 daily trigger(s). No tasks installed.\n'
    assert out.err == ''
    assert legacy.main(['--config-file', str(path)]) == 1
    out = capsys.readouterr()
    assert out.out == '' and 'SECRET' not in out.err


def test_late_invalid_task_no_partial_output(tmp_path, capsys):
    path = write(tmp_path, '[Task1]\naction=["python"]\n[Task2]\naction=SECRET\n')
    assert legacy.main(['--config-file', str(path), '--dry-run']) == 2
    out = capsys.readouterr()
    assert out.out == '' and 'SECRET' not in out.err


def test_missing_file(tmp_path):
    with pytest.raises(SchedulerError):
        legacy.parse_config(tmp_path / 'missing')


def test_unsupported_os(tmp_path, monkeypatch):
    path = write(tmp_path, '[Task1]\naction=["python"]\n')
    monkeypatch.setattr(app, 'sys', SimpleNamespace(platform='unknown'))
    with pytest.raises(SchedulerError):
        legacy.plan_tasks(path)


@pytest.mark.parametrize('entry', ['module', 'script'])
def test_entry_outside_repo(tmp_path, monkeypatch, entry):
    from pathlib import Path
    import sys
    root = Path(__file__).resolve().parents[1]
    path = write(tmp_path, '[Task1]\naction=["python"]\nhours=0\nminutes=0\n')
    (tmp_path / 'sitecustomize.py').write_text(
        'import os,subprocess\ndef blocked(*a,**k): raise RuntimeError("native operation blocked")\n'
        'os.system=blocked\nsubprocess.run=blocked\n', encoding='utf-8')
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(tmp_path), str(root)]), PYTHONDONTWRITEBYTECODE='1')
    monkeypatch.undo()
    command = [sys.executable, '-m', 'UTaskScheduler.scheduler'] if entry == 'module' else [sys.executable, str(root / 'UTaskScheduler' / 'scheduler.py')]
    result = subprocess.run(command + ['--config-file', str(path), '--dry-run'], cwd=tmp_path,
                            env=env, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'Validated 1 task(s), 1 daily trigger(s). No tasks installed.\n'
