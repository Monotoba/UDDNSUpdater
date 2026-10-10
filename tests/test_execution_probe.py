import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime

import pytest

from UTaskScheduler.execution_probe import main, write_probe


def test_probe_records_arguments_and_execution_context(tmp_path):
    arguments = ['two words', 'quote"here', '100%', '', 'λ', '--flag']
    first = write_probe(tmp_path, arguments)
    original = first.read_bytes()
    second = write_probe(tmp_path, ['next run'])
    assert first != second
    assert first.read_bytes() == original
    record = json.loads(original)
    assert record['schema_version'] == 1
    assert record['arguments'] == arguments
    assert record['pid'] == os.getpid()
    assert record['executable'] == sys.executable
    assert record['working_directory'] == str(Path.cwd())
    assert datetime.fromisoformat(record['timestamp_utc']).utcoffset().total_seconds() == 0
    if os.name == 'posix':
        assert first.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('directory', ['relative', 'missing'])
def test_probe_rejects_invalid_directory(tmp_path, directory):
    path = directory if directory == 'relative' else tmp_path / directory
    with pytest.raises(ValueError):
        write_probe(path, [])
    assert not list(tmp_path.iterdir())


def test_probe_reports_write_failure_without_arguments(tmp_path, capsys, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError('sensitive OS detail')
    monkeypatch.setattr(os, 'open', fail)
    assert main(['--output-directory', str(tmp_path), '--', 'private-argument']) == 1
    captured = capsys.readouterr()
    assert captured.out == ''
    assert captured.err == 'Scheduler probe could not write execution evidence.\n'


@pytest.mark.parametrize("alias_cwd", [False, True])
def test_probe_module_runs_outside_checkout(tmp_path, alias_cwd):
    output = tmp_path / 'output'
    output.mkdir()
    working_directory = tmp_path
    if alias_cwd:
        working_directory = tmp_path / 'cwd-alias'
        try:
            working_directory.symlink_to(tmp_path, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip('Directory symlinks unavailable for this user.')
    environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    result = subprocess.run(
        [sys.executable, '-m', 'UTaskScheduler.execution_probe',
         '--output-directory', str(output), '--', 'two words', '100%', '--flag'],
        cwd=working_directory, env=environment, capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == result.stderr == ''
    files = list(output.glob('uddns-probe-*.json'))
    assert len(files) == 1
    record = json.loads(files[0].read_text())
    assert record['arguments'] == ['two words', '100%', '--flag']
    assert record['working_directory'] == str(working_directory.resolve())


def test_probe_never_overwrites_existing_record(tmp_path, monkeypatch):
    import UTaskScheduler.execution_probe as probe
    class FixedID:
        hex = 'fixed'
    monkeypatch.setattr(probe, 'uuid4', lambda: FixedID())
    first = write_probe(tmp_path, ['first'])
    original = first.read_bytes()
    with pytest.raises(FileExistsError):
        write_probe(tmp_path, ['second'])
    assert first.read_bytes() == original


def test_probe_rejects_symlink_directory(tmp_path):
    target = tmp_path / 'target'
    target.mkdir()
    link = tmp_path / 'link'
    try:
        link.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip('Directory symlinks unavailable for this user.')
    with pytest.raises(ValueError):
        write_probe(link, [])
    assert not list(target.iterdir())
