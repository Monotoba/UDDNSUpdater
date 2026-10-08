import importlib
import os
from pathlib import Path
import subprocess
import sys

import pytest
import requests

ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = sorted(p.stem for p in (ROOT / "providers").glob("provider_*.py"))


@pytest.fixture(autouse=True)
def prohibit_requests(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail("Real HTTP requests are prohibited in tests")
    monkeypatch.setattr(requests.sessions.Session, "request", blocked)


@pytest.mark.parametrize("module_name", PROVIDERS)
def test_provider_import_uses_shared_base(module_name):
    from providers.ddns_provider import DDNSProvider
    module = importlib.import_module(f"providers.{module_name}")
    classes = [cls for cls in vars(module).values()
               if isinstance(cls, type) and cls.__module__ == module.__name__]
    assert len(classes) == 1
    assert issubclass(classes[0], DDNSProvider)


def test_discovery_outside_checkout(monkeypatch, tmp_path):
    import ddns_updater
    monkeypatch.chdir(tmp_path)
    classes = ddns_updater.load_provider_classes()
    assert len(classes) == len(PROVIDERS)
    assert "NamecheapDDNS" in classes
    assert "GoDaddyDDNS" in classes
    assert "DDNSProvider" not in classes
    assert list(tmp_path.iterdir()) == []


def test_legacy_discovery_matches_main(monkeypatch, tmp_path):
    import ddns_updater
    from providers.ddns_provider import load_provider_classes
    monkeypatch.chdir(tmp_path)
    assert load_provider_classes() == ddns_updater.load_provider_classes()


@pytest.mark.parametrize("module_mode", [False, True], ids=["script", "module"])
def test_help_outside_checkout_has_no_side_effects(tmp_path, module_mode):
    # Block HTTP in the child too: importing sitecustomize requires no changes
    # to application code and covers any accidental request during startup.
    hook = tmp_path / "sitecustomize.py"
    hook.write_text("import requests\ndef blocked(*a, **k):\n    raise RuntimeError('HTTP prohibited')\nrequests.sessions.Session.request = blocked\n")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(tmp_path), str(ROOT)])
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    command = [sys.executable]
    command += ["-m", "ddns_updater"] if module_mode else [str(ROOT / "ddns_updater.py")]
    result = subprocess.run(command + ["--help"], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert "--no-log" in result.stdout
    assert set(p.name for p in tmp_path.iterdir()) == {"sitecustomize.py"}
