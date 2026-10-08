# UDDNSUpdater

[![Tests](https://github.com/Monotoba/UDDNSUpdater/actions/workflows/tests.yml/badge.svg)](https://github.com/Monotoba/UDDNSUpdater/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Status](https://img.shields.io/badge/status-work%20in%20progress-orange)
[![License](https://img.shields.io/badge/license-BSD--2--Clause-blue)](LICENSE)

A Python prototype for updating dynamic-DNS records through multiple provider
adapters, with a separate experimental task-scheduling component.

**Work in progress — not ready for unattended or production use.** Provider
loading, configuration validation, dry runs, and CLI failure handling have an offline
test baseline. Namecheap/DuckDNS/No-IP/Dynu/ChangeIP/Securepoint/SpDYN/YDNS request encoding and response checks have offline
coverage. Live provider requests, credentials, DNS propagation, and native
scheduling have not been validated.
There is no release or PyPI package.

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
Namecheap, DuckDNS, No-IP, Dynu, ChangeIP, Securepoint, SpDYN, and YDNS now check response bodies and report provider acceptance.
The other 8 adapters still have legacy request/response behavior. A zero exit
code for those adapters only means they returned without raising; it does not
establish provider success. No adapter verifies DNS propagation.
See [provider repair status](docs/PROVIDERS.md).

The scheduler modules have incompatible method/constructor signatures. Do not
use them to install system tasks yet. See [ROADMAP.md](ROADMAP.md) for the repair
order and [CONTRIBUTING.md](CONTRIBUTING.md) for test expectations.

## Contribute

Start with provider/configuration validation, mocked HTTP behavior, or scheduler
command generation. Report expected and actual behavior, OS/Python version, and
sanitized reproduction steps through [issues](https://github.com/Monotoba/UDDNSUpdater/issues).
Do not share credentials, raw provider errors, or password-bearing URLs.

Licensed under [BSD-2-Clause](LICENSE).
