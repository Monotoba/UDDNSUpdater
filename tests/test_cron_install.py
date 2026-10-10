from types import SimpleNamespace
import subprocess
import pytest
from UTaskScheduler.schedulers import cron_install as cron
from UTaskScheduler.schedulers.scheduler_unix import CronPreviewError
from UTaskScheduler import utask_scheduler as app

PREVIEW = 'SHELL=/bin/sh\n0 0 * * * /usr/bin/true\n'

@pytest.mark.parametrize('existing', ['', '# unrelated\n5 2 * * * other\n', 'SHELL=/bin/bash\n# keep'])
def test_replace_remove_preserves_existing(existing):
    installed = cron.replace_block(existing, 'test', PREVIEW)
    assert installed.startswith(existing)
    assert installed.count('# BEGIN UDDNSUpdater test') == 1
    assert cron.replace_block(installed, 'test', PREVIEW) == installed
    removed = cron.replace_block(installed, 'test')
    assert removed == existing+('' if not existing or existing.endswith('\n') else '\n')

@pytest.mark.parametrize('name', ['', '../x', 'a\nb', 'x'*65, None])
def test_invalid_names_before_native_calls(name, monkeypatch):
    monkeypatch.setattr(cron.subprocess, 'run', lambda *a, **k: pytest.fail('Native call'))
    with pytest.raises(CronPreviewError):
        cron.apply(name, PREVIEW)

@pytest.mark.parametrize('existing', ['# BEGIN UDDNSUpdater test\n', '# END UDDNSUpdater test\n', '# END UDDNSUpdater test\n# BEGIN UDDNSUpdater test\n'])
def test_corrupt_markers_fail_closed(existing):
    with pytest.raises(CronPreviewError):
        cron.replace_block(existing, 'test', PREVIEW)

def test_apply_verifies_and_is_idempotent(monkeypatch):
    current = {'text': '# keep\n'}
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        assert kwargs['timeout'] == 15 and 'shell' not in kwargs
        if argv == ['crontab', '-']:
            current['text'] = kwargs['input']
        return SimpleNamespace(returncode=0, stdout=current['text'])
    monkeypatch.setattr(cron.subprocess, 'run', run)
    assert cron.apply('test', PREVIEW)
    assert not cron.apply('test', PREVIEW)
    assert calls.count(['crontab', '-']) == 1
    assert cron.apply('test')
    assert current['text'] == '# keep\n'

@pytest.mark.parametrize('failure', [1, subprocess.TimeoutExpired('crontab', 15), OSError('SECRET')])
def test_read_failures_never_write(monkeypatch, failure):
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        if isinstance(failure, Exception):
            raise failure
        return SimpleNamespace(returncode=failure, stdout='SECRET')
    monkeypatch.setattr(cron.subprocess, 'run', run)
    with pytest.raises(CronPreviewError) as error:
        cron.apply('test', PREVIEW)
    assert calls == [['crontab', '-l']]
    assert 'SECRET' not in str(error.value)

def test_cli_explicit_install_and_remove(tmp_path, monkeypatch):
    monkeypatch.setattr(app.sys, 'platform', 'linux')
    path = tmp_path/'schedule.ini'
    path.write_text('[SCHEDULE]\nHour=0\nMinute=0\n')
    calls = []
    monkeypatch.setattr(cron, 'apply', lambda *args: calls.append(args))
    assert app.main(['--config-file', str(path), '--install-cron', 'test', '--', '/usr/bin/true']) == 0
    assert calls == [('test', PREVIEW)]
    assert app.main(['--remove-cron', 'test']) == 0
    assert calls[-1] == ('test', None)

@pytest.mark.parametrize('write_status,verified', [(1, ''), (0, 'wrong')])
def test_write_or_verification_failure_is_reported(monkeypatch, write_status, verified):
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        if argv == ['crontab', '-']:
            return SimpleNamespace(returncode=write_status, stdout='SECRET')
        return SimpleNamespace(returncode=0, stdout='' if len(calls)==1 else verified)
    monkeypatch.setattr(cron.subprocess, 'run', run)
    with pytest.raises(CronPreviewError) as error:
        cron.apply('test', PREVIEW)
    assert 'SECRET' not in str(error.value)


def test_nonlinux_rejected_before_native_operation(monkeypatch):
    monkeypatch.setattr(app.sys, 'platform', 'win32')
    monkeypatch.setattr(cron, 'apply', lambda *a: pytest.fail('Native call'))
    assert app.main(['--remove-cron', 'test']) == 2
