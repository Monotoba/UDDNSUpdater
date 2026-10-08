import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from types import SimpleNamespace

import pytest

from UTaskScheduler import utask_scheduler as app
from UTaskScheduler.schedulers.scheduler_unix import UnixTaskScheduler, CronPreviewError

ROOT = Path(__file__).resolve().parents[1]
SPECIAL = ['space here', "single'quote", '"double"', '$(printf HACKED)', '`printf HACKED`',
    '; printf HACKED; #', '$HOME', '*', '', '%', 'a%%b', r'\%', r'\\%', 'end\\',
    'tab\there', 'café', "quote'\\%end"]


@pytest.fixture(autouse=True)
def prohibit_native_actions(monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail('Native task action prohibited')
    monkeypatch.setattr(subprocess, 'run', fail)
    monkeypatch.setattr(os, 'system', fail)
    monkeypatch.setattr(app, 'sys', SimpleNamespace(platform='linux', stderr=sys.stderr))


def cron_command_for_shell(command):
    """Model cron's escape scan independently of the quoting renderer.

    Cronie do_command.c removes only the backslash escaping a percent and splits
    on unescaped percent, before /bin/sh sees quote characters.
    """
    output = []
    index = 0
    while index < len(command):
        char = command[index]
        if char == '%':
            pytest.fail('Unescaped percent would split command/stdin')
        if char == '\\' and index+1 < len(command):
            following = command[index+1]
            if following != '%':
                output.append(char)
            output.append(following)
            index += 2
        else:
            output.append(char)
            index += 1
    return ''.join(output)


@pytest.mark.parametrize('arg', SPECIAL)
def test_arguments_survive_cron_and_shell_parsing(arg):
    action = ['/path with spaces/python', '/script.py', arg]
    line = UnixTaskScheduler([6,15], action).render_cron_line()
    fields = line.split(' ',5)
    assert fields[:5] == ['15','6','*','*','*']
    assert shlex.split(cron_command_for_shell(fields[5])) == action


def test_definition_has_shell_and_final_newline():
    definition = UnixTaskScheduler([0,0], ['/usr/bin/python3','/job.py']).render_cron()
    assert definition == 'SHELL=/bin/sh\n0 0 * * * /usr/bin/python3 /job.py\n'


@pytest.mark.parametrize('schedule', [None, [], [0], [0,0,0], ['*',0], [True,0],
    [24,0], [-1,0], [0,60], [0,-1]])
def test_invalid_time_is_rejected(schedule):
    with pytest.raises(CronPreviewError):
        UnixTaskScheduler(schedule, ['/bin/true']).render_cron()


@pytest.mark.parametrize('action', [None, [], 'python /job.py', ['python'], [''],
    ['/bin/true', None], ['/bin/true', 'bad\nargument'], ['/bin/true', 'bad\x00argument']])
def test_invalid_command_is_rejected(action):
    with pytest.raises(CronPreviewError):
        UnixTaskScheduler([0,0], action).render_cron()


def test_system_crontab_not_silently_generated_as_user_entry():
    with pytest.raises(CronPreviewError, match='System crontab'):
        UnixTaskScheduler([0,0], ['/bin/true'], system_task=True).render_cron()


def test_direct_backend_installation_is_blocked():
    scheduler = UnixTaskScheduler([0,0], ['/bin/true'])
    assert scheduler.schedule(dry_run=True) == scheduler.render_cron()
    assert scheduler.schedule_linux(dry_run=True) == scheduler.render_cron()
    for call in [scheduler.schedule, scheduler.schedule_linux, scheduler.schedule_macos]:
        with pytest.raises(CronPreviewError, match='unavailable'):
            call()


def write_config(tmp_path, text='[SCHEDULE]\nHour=*/6\nMinute=*/15'):
    path = tmp_path/'schedule.ini'
    path.write_text(text)
    return path


def test_unified_preview_covers_all_triggers_without_writes(tmp_path):
    path = write_config(tmp_path)
    preview = app.UTaskScheduler(path).preview_cron(['/bin/true'])
    lines = preview.splitlines()
    assert lines[0] == 'SHELL=/bin/sh'
    assert len(lines) == 17
    assert {tuple(line.split(' ',2)[:2]) for line in lines[1:]} == {
        (str(m),str(h)) for h in [0,6,12,18] for m in [0,15,30,45]}
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize('tag', ['win32','darwin'])
def test_preview_rejects_non_linux_schedule(tmp_path, monkeypatch, tag):
    monkeypatch.setattr(app, 'sys', SimpleNamespace(platform=tag, stderr=sys.stderr))
    with pytest.raises(app.SchedulerError, match='only for Linux'):
        app.UTaskScheduler(write_config(tmp_path)).preview_cron(['/bin/true'])


@pytest.mark.parametrize('action,config', [(['relative'], '[SCHEDULE]'),
    (['/bin/true'], '[SCHEDULE]\nMinute=*/0')])
def test_cli_preview_errors_do_not_print_partial_definition(tmp_path, capsys, action, config):
    path = write_config(tmp_path, config)
    assert app.main(['--config-file',str(path),'--preview-cron','--',*action]) == 2
    output = capsys.readouterr()
    assert output.out == ''
    assert 'relative' not in output.err


def test_cli_preview_is_explicit_and_preserves_arguments(tmp_path, capsys):
    path = write_config(tmp_path, '[SCHEDULE]\nHour=0\nMinute=15')
    action = ['/bin/echo', *SPECIAL]
    assert app.main(['--config-file',str(path),'--preview-cron','--',*action]) == 0
    output = capsys.readouterr()
    assert not output.err
    assert output.out.startswith('SHELL=/bin/sh\n15 0 * * * ')
    command = output.out.splitlines()[1].split(' ',5)[5]
    assert shlex.split(cron_command_for_shell(command)) == action
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.skipif(sys.platform == 'win32', reason='Requires local /bin/sh for harmless argv round trip')
def test_actual_shell_preserves_arguments_after_cron_decode(monkeypatch):
    monkeypatch.undo()
    action = [sys.executable,'-c','import json,sys;print(json.dumps(sys.argv[1:]))', *SPECIAL]
    line = UnixTaskScheduler([0,0], action).render_cron_line()
    command = cron_command_for_shell(line.split(' ',5)[5])
    result = subprocess.run(['/bin/sh','-c',command], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == SPECIAL


@pytest.mark.skipif(sys.platform != 'linux', reason='CLI preview intentionally requires Linux')
def test_module_and_direct_script_preview_outside_repo(tmp_path, monkeypatch):
    monkeypatch.undo()
    path = write_config(tmp_path, '[SCHEDULE]\nHour=0\nMinute=15')
    hook = tmp_path/'sitecustomize.py'
    hook.write_text("import os,subprocess\ndef fail(*a,**k):\n    raise RuntimeError('Native task mutation prohibited')\nos.system=fail\nsubprocess.run=fail\n")
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join([str(tmp_path),str(ROOT)])
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    for entry in [['-m','UTaskScheduler.utask_scheduler'], [str(ROOT/'UTaskScheduler/utask_scheduler.py')]]:
        result = subprocess.run([sys.executable,*entry,'--config-file',str(path),'--preview-cron','--','/bin/true'],
            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stderr
        assert result.stdout == 'SHELL=/bin/sh\n15 0 * * * /bin/true\n'
    assert set(p.name for p in tmp_path.iterdir()) == {'schedule.ini','sitecustomize.py'}
