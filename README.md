# UDDNSUpdater

[![Tests](https://github.com/Monotoba/UDDNSUpdater/actions/workflows/tests.yml/badge.svg)](https://github.com/Monotoba/UDDNSUpdater/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Status](https://img.shields.io/badge/status-alpha-orange)
[![License](https://img.shields.io/badge/license-BSD--2--Clause-blue)](LICENSE)

A Python prototype for updating dynamic-DNS records through multiple provider
adapters, with a separate experimental task-scheduling component.

**Work in progress — not ready for unattended or production use.** Provider
loading, configuration validation, dry runs, and CLI failure handling have an offline
test baseline. The repaired adapters request encoding and response checks have offline
coverage. Main has live DuckDNS update/restoration evidence and native Linux cron
and macOS launchd execution evidence, plus Linux systemd user-timer and Windows
Task Scheduler execution. Other providers and user-specific unattended environments
still require validation; see the checklist below.
Version 0.1.0a2 is an experimental alpha with explicit native scheduler installation. PyPI publication is on hold.

## Evaluate the alpha

Version `0.1.0a2` remains an alpha. See [GitHub releases](https://github.com/Monotoba/UDDNSUpdater/releases). PyPI publication is on hold. Install from this checkout with `python -m pip install .`, then run
`uddns-updater --config-file examples/evaluation.ini --dry-run` for an offline
configuration check. See [alpha scope and installation](docs/ALPHA.md).

## Start with development checks

Use Python 3.10+ in an activated virtual environment:

```sh
git clone https://github.com/Monotoba/UDDNSUpdater.git
cd UDDNSUpdater
python -m pip install -r requirements-dev.txt
python -m pytest -q
python ddns_updater.py --help
```

The help command and `--dry-run` do not contact providers or write log files.
Use `python ddns_updater.py --config-file /path/to/settings.ini --dry-run` to
validate a configuration. See [CLI configuration and status codes](docs/CLI.md).
Running without `--help` or `--dry-run` can send real DNS update requests; avoid
real credentials during development. The default config path is `config.ini`
in the current directory.

## Current implementation

Sixteen provider adapter modules exist in `providers/`. Their presence does not
establish working service support. Configuration selects the exact Python class
name, such as `NamecheapDDNS`, rather than the lowercase names in the old manual.
Provider loading now resolves the bundled directory independently of the working
directory. Imports use one shared base class.

`--no-log` disables file logging; controlled errors still print to stderr.
`--config-file` selects a UTF-8 INI file, and `--dry-run` checks all service
sections before any provider is constructed. Raw adapter output is suppressed
by the CLI because it may contain provider response bodies or credentials.
The older manuals remain design drafts, not validated operating instructions.
Fourteen adapter classes now check responses and report provider acceptance.
GoogleDomains and DNSMax are retained but disabled: migrated Google domains no
longer support DDNS, and DNSMax has closed.
All active adapters now raise controlled failures for unrecognized or rejected
responses. Response checks are offline-tested; several provider contracts still
need live confirmation. No adapter verifies DNS propagation.
See [provider repair status](docs/PROVIDERS.md).

The unified scheduler validates daily schedules and provides Linux, macOS, and
Windows previews. Main supports explicit named task installation/removal on
all three platforms, with a choice of cron or systemd user timers on Linux.
Use `--scheduler cron` or `--scheduler systemd` with `--preview NAME`,
`--install NAME`, `--status NAME`, or `--remove NAME`. Existing cron-specific
commands remain supported. Native evidence is tracked per platform. Version 0.1.0a2
includes these explicit installation modes; 0.1.0a1 had previews only. See [scheduler validation](docs/SCHEDULER.md), the
[1.0 validation checklist](docs/RELEASE_VALIDATION.md), and
[CONTRIBUTING.md](CONTRIBUTING.md).

## Contribute

Start with provider/configuration validation, mocked HTTP behavior, or scheduler
command generation. Report expected and actual behavior, OS/Python version, and
sanitized reproduction steps through [issues](https://github.com/Monotoba/UDDNSUpdater/issues).
Do not share credentials, raw provider errors, or password-bearing URLs.

Licensed under [BSD-2-Clause](LICENSE).

macOS scheduler definitions can now be inspected with `--preview-launchd`; see
[the scheduler guide](docs/SCHEDULER.md) for explicit main-branch registration.

Windows scheduler XML can now be inspected with `--preview-windows --start-date YYYY-MM-DD`;
see [the scheduler guide](docs/SCHEDULER.md) for explicit main-branch registration.

Legacy TaskN configurations now support validated daily planning with
`python -m UTaskScheduler.scheduler --config-file tasks.ini --dry-run`.
See [the scheduler guide](docs/SCHEDULER.md); installation remains unavailable.

Opt-in [persistent change detection](docs/UPDATE_STATE.md) is implemented via
`--state-file /absolute/path/to/state.json --refresh-seconds N`. No-IP/Dynu stop/cooldown persistence and SecurePoint/SpDYN/YDNS/ChangeIP/EuroDynDNS/Namecheap/DuckDNS/FreeDNS/Afraid/CloudNS/EntryDNS/GoDaddy conservative stops
are implemented; these providers require the state options for normal updates. All active bundled CLI adapters require state options. Shared transport failures
use a provider-scoped 30-minute cooldown. Unattended operation remains unvalidated.
