"""Install a built wheel outside the checkout and verify offline entry points."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv
import zipfile


def check(wheel):
    wheel = Path(wheel).resolve()
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        for name in ('ddns_updater.py', 'update_state.py', 'providers/provider_duckddns.py',
                     'UTaskScheduler/utask_scheduler.py', 'UTaskScheduler/execution_probe.py'):
            assert name in names, name
        assert any(name.endswith('/licenses/LICENSE') for name in names)
        assert not any(name.startswith('tests/') for name in names)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        # Verify dependency resolution in a fresh environment before blocking HTTP.
        venv.EnvBuilder(with_pip=True, system_site_packages=False).create(root/'venv')
        python = root/'venv'/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        command = root/'venv'/('Scripts/uddns-updater.exe' if os.name == 'nt' else 'bin/uddns-updater')
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        def run(arguments):
            result = subprocess.run(arguments, cwd=root, env=env,
                                    capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError(result.stderr)
            return result.stdout
        run([str(python), '-m', 'pip', 'install', str(wheel)])
        config = root/'evaluation.ini'
        config.write_text('[evaluation]\nddns_provider=DuckDNS\nsubdomain=evaluation\ntoken=evaluation-token\n')
        # Any accidental network request causes the check to fail immediately.
        hook = root/'sitecustomize.py'
        hook.write_text("import requests\ndef blocked(*a, **k):\n    raise AssertionError('Network forbidden during distribution checks')\nrequests.sessions.Session.request = blocked\n")
        env['PYTHONPATH'] = str(root)
        assert 'usage:' in run([str(command), '--help'])
        for launcher in ([str(command)], [str(python), '-m', 'ddns_updater']):
            run(launcher+['--config-file', str(config), '--dry-run'])
        code = "from pathlib import Path; import ddns_updater; assert Path(ddns_updater.__file__).resolve().is_relative_to(Path('venv').resolve()); from providers.ddns_provider import load_provider_classes; assert len(load_provider_classes()) == 16"
        run([str(python), '-c', code])
        assert not (root/'ddns_update.log').exists()
        assert not list(root.glob('*.json'))
        probe_directory = root/'probe-output'
        probe_directory.mkdir()
        run([str(python), '-m', 'UTaskScheduler.execution_probe',
             '--output-directory', str(probe_directory), '--', 'two words', '100%', '--flag'])
        records = list(probe_directory.glob('uddns-probe-*.json'))
        assert len(records) == 1
        record = json.loads(records[0].read_text(encoding='utf-8'))
        assert record['arguments'] == ['two words', '100%', '--flag']
        assert Path(record['executable']).resolve() == python.resolve()
        assert record['working_directory'] == str(root)

    print('Installed-wheel offline checks passed.')


if __name__ == '__main__':
    check(sys.argv[1])
