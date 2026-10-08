from pathlib import Path
import os
import subprocess
import sys

import pytest
import requests

import ddns_updater as app

ROOT = Path(__file__).resolve().parents[1]
SECRET = "secret%with&characters"
SCHEMAS = {
    "Afraid": ("api_key", "hostname"),
    "ChangeIP": ("username", "password", "hostname"),
    "CloudNS": ("username", "password", "hostname"),
    "DNSMax": ("username", "password", "hostname"),
    "DuckDNS": ("subdomain", "token"),
    "Dynu": ("username", "password", "hostname"),
    "EntryDNS": ("username", "password", "hostname"),
    "EuroDynDNS": ("username", "password", "hostname"),
    "FreeDNS": ("api_key", "hostname"),
    "GoDaddyDDNS": ("api_key", "api_secret", "domain", "hostname"),
    "GoogleDomains": ("api_key", "hostname"),
    "NamecheapDDNS": ("domain", "password", "hostname"),
    "NoIP": ("username", "password", "hostname"),
    "SecurePoint": ("username", "password", "hostname"),
    "SpDYN": ("username", "password", "hostname"),
    "YDNS": ("hostname", "username", "password"),
}


@pytest.fixture(autouse=True)
def isolation(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    def blocked(*args, **kwargs):
        pytest.fail("Real HTTP requests are prohibited")
    monkeypatch.setattr(requests.sessions.Session, "request", blocked)


def config(text):
    path = Path("custom.ini")
    path.write_text(text, encoding="utf-8")
    return path


def namecheap(section="service"):
    return f"[{section}]\nddns_provider=NamecheapDDNS\ndomain=example.net\nhostname=@\npassword={SECRET}\n"


@pytest.mark.parametrize("provider", SCHEMAS)
def test_all_builtin_dry_runs_do_not_construct_providers(provider, monkeypatch):
    classes = app.load_provider_classes()
    def blocked(*args, **kwargs):
        pytest.fail("Dry run constructed a provider")
    monkeypatch.setattr(app.DDNSProvider, "__init__", blocked)
    path = config("[service]\nddns_provider=" + provider + "\n" +
                  "\n".join(f"{key}={SECRET}" for key in SCHEMAS[provider]))
    assert app.main(["--config-file", str(path), "--dry-run"]) == (2 if provider == "GoogleDomains" else 0)
    assert set(p.name for p in Path.cwd().iterdir()) == {"custom.ini"}
    assert classes[provider].required_fields == SCHEMAS[provider]


@pytest.mark.parametrize("provider,key", [(p, k) for p, keys in SCHEMAS.items() if p != "GoogleDomains" for k in keys])
def test_required_fields_checked_before_network(provider, key, capsys):
    path = config("[service]\nddns_provider=" + provider + "\n" +
                  "\n".join(f"{k}=value" for k in SCHEMAS[provider] if k != key))
    assert app.main(["--config-file", str(path)]) == 2
    assert key in capsys.readouterr().err
    assert not Path("ddns_update.log").exists()


@pytest.mark.parametrize("text", ["", "[DEFAULT]\npassword=secret", "not an ini secret",
                                 "[service]\npassword=secret", "[service]\nddns_provider=secret",
                                 "[secret]\na=1\na=2", "[secret]\n[secret]\n"])
def test_invalid_files_are_sanitized_and_do_not_create_logs(text, capsys):
    path = config(text)
    assert app.main(["--config-file", str(path)]) == 2
    output = capsys.readouterr()
    assert "secret" not in output.out + output.err
    assert not Path("ddns_update.log").exists()


@pytest.mark.parametrize("value", ["", "   ", "YOUR_PASSWORD", "your_token"])
def test_blank_and_placeholder_values_rejected(value):
    path = config(namecheap().replace(SECRET, value))
    assert app.main(["--config-file", str(path), "--dry-run"]) == 2


def test_missing_and_non_utf8_files(capsys):
    assert app.main(["--config-file", "secret-does-not-exist"]) == 2
    Path("invalid.ini").write_bytes(b"\xffsecret")
    assert app.main(["--config-file", "invalid.ini"]) == 2
    assert "secret" not in capsys.readouterr().err


def test_literal_percent_credentials_preserved():
    path = config(namecheap())
    services = app.load_services(path, app.load_provider_classes())
    assert services[0][2]["password"] == SECRET


def test_invalid_later_service_prevents_all_updates(monkeypatch):
    def blocked(*a, **k):
        pytest.fail("Validation must finish before any construction")
    monkeypatch.setattr(app.DDNSProvider, "__init__", blocked)
    config(namecheap() + "\n[later]\nddns_provider=Unknown\n")
    assert app.main(["--config-file", "custom.ini"]) == 2


def fake_registry(monkeypatch, fail_at=None):
    calls = []
    class Fake:
        required_fields = ("password",)
        def __init__(self, name, settings):
            calls.append(("init", name, settings["password"]))
            print(SECRET)
            if fail_at == "init":
                raise RuntimeError(SECRET)
        def update_ddns(self):
            calls.append(("update",))
            print("Response: " + SECRET, file=sys.stderr)
            if fail_at == "update":
                raise RuntimeError("https://example.net/?password=" + SECRET)
    monkeypatch.setattr(app, "load_provider_classes", lambda: {"Fake": Fake})
    config(f"[{SECRET}]\nddns_provider=Fake\npassword={SECRET}\n")
    return calls


@pytest.mark.parametrize("phase", ["init", "update"])
@pytest.mark.parametrize("no_log", [False, True])
def test_runtime_failures_and_raw_provider_output_are_sanitized(monkeypatch, capsys, phase, no_log):
    calls = fake_registry(monkeypatch, phase)
    assert app.main(["--config-file", "custom.ini"] + (["--no-log"] if no_log else [])) == 1
    output = capsys.readouterr()
    assert SECRET not in output.out + output.err
    assert "Service 1: update failed" in output.err
    log = Path("ddns_update.log")
    assert log.exists() == (not no_log)
    if not no_log:
        assert SECRET not in log.read_text()
        log.unlink()  # Verifies the handler is closed, including on Windows.
    assert len(calls) == (1 if phase == "init" else 2)


def test_default_config_and_adapter_completion_are_honest(monkeypatch, capsys):
    calls = fake_registry(monkeypatch)
    Path("custom.ini").rename("config.ini")
    assert app.main(["--no-log"]) == 0
    output = capsys.readouterr()
    assert SECRET not in output.out + output.err
    assert "provider success is not yet verified" in output.out
    assert len(calls) == 2


def test_log_open_failure_prevents_updates(monkeypatch, capsys):
    calls = fake_registry(monkeypatch)
    def fail(*a, **k):
        raise OSError(SECRET)
    monkeypatch.setattr(app.logging, "FileHandler", fail)
    assert app.main(["--config-file", "custom.ini"]) == 1
    assert not calls
    assert SECRET not in capsys.readouterr().err


def test_discovery_failure_sanitized(monkeypatch, capsys):
    def fail():
        raise RuntimeError(SECRET)
    monkeypatch.setattr(app, "load_provider_classes", fail)
    assert app.main(["--dry-run"]) == 1
    assert SECRET not in capsys.readouterr().err


def test_later_services_run_after_failure(monkeypatch, capsys):
    calls = []
    class Fake:
        required_fields = ("password",)
        def __init__(self, name, settings):
            self.name = name
        def update_ddns(self):
            calls.append(self.name)
            if self.name == "first":
                raise RuntimeError(SECRET)
    monkeypatch.setattr(app, "load_provider_classes", lambda: {"Fake": Fake})
    config(f"[first]\nddns_provider=Fake\npassword={SECRET}\n"
           f"[second]\nddns_provider=Fake\npassword={SECRET}\n")
    assert app.main(["--config-file", "custom.ini", "--no-log"]) == 1
    assert calls == ["first", "second"]
    assert SECRET not in capsys.readouterr().err


@pytest.mark.parametrize("phase", ["write", "flush", "close"])
def test_log_failures_do_not_leak_exception_context(monkeypatch, capsys, phase):
    fake_registry(monkeypatch, "update" if phase != "close" else None)
    class Handler:
        stream = None
        closed = False
        def __init__(self, *args, **kwargs):
            self.stream = self
        def setFormatter(self, formatter):
            self.formatter = formatter
        def format(self, record):
            return self.formatter.format(record)
        def write(self, text):
            if phase == "write":
                raise OSError(SECRET)
        def flush(self):
            if phase == "flush":
                raise OSError(SECRET)
        def close(self):
            self.closed = True
            if phase == "close":
                raise OSError(SECRET)
    handler = Handler()
    monkeypatch.setattr(app.logging, "FileHandler", lambda *a, **k: handler)
    assert app.main(["--config-file", "custom.ini"]) == 1
    output = capsys.readouterr()
    assert SECRET not in output.out + output.err
    assert "Cannot" in output.err
    assert handler.closed


def test_legacy_main_uses_same_validation():
    from providers.ddns_provider import main
    config(namecheap())
    assert main(["--config-file", "custom.ini", "--dry-run"]) == 0


@pytest.mark.parametrize("arguments,expected", [(["--dry-run"], 0), ([], 2)])
def test_script_exit_codes_and_dry_run_in_child(tmp_path, arguments, expected):
    path = config(namecheap() if expected == 0 else "[bad]\nddns_provider=unknown\n")
    hook = tmp_path / "sitecustomize.py"
    hook.write_text("import requests\ndef blocked(*a, **k):\n    raise RuntimeError('HTTP prohibited')\nrequests.sessions.Session.request = blocked\n")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(tmp_path), str(ROOT)])
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run([sys.executable, str(ROOT / "ddns_updater.py"),
                             "--config-file", str(path), *arguments],
                            env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == expected, result.stderr
    assert SECRET not in result.stdout + result.stderr
    assert not Path("ddns_update.log").exists()
