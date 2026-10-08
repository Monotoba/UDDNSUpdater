# UDDNSUpdater

[![Tests](https://github.com/Monotoba/UDDNSUpdater/actions/workflows/tests.yml/badge.svg)](https://github.com/Monotoba/UDDNSUpdater/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Status](https://img.shields.io/badge/status-work%20in%20progress-orange)
[![License](https://img.shields.io/badge/license-BSD--2--Clause-blue)](LICENSE)

A Python prototype for updating dynamic-DNS records through multiple provider
adapters, with a separate experimental task-scheduling component.

**Work in progress — not ready for unattended or production use.** Provider
loading and help commands have an offline test baseline. Live provider requests,
credentials, response validation, and native scheduling have not been validated.
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

The help command does not contact providers or write log files. This project has
no dry-run option. Running without `--help` reads `config.ini` from the current
directory and can send real DNS update requests; avoid real credentials during
development. Config files and logs can contain sensitive information.

## Current implementation

Sixteen provider adapter modules exist in `providers/`. Their presence does not
establish working service support. Configuration selects the exact Python class
name, such as `NamecheapDDNS`, rather than the lowercase names in the old manual.
Provider loading now resolves the bundled directory independently of the working
directory. Imports use one shared base class.

`--no-log` is the only application option besides `--help`; it disables file
logging, but errors still print to stderr. Legacy logging/config-file flags
described in the manual are not implemented. The manuals are design drafts with
unfinished examples, not validated operating instructions.

The scheduler modules have incompatible method/constructor signatures. Do not
use them to install system tasks yet. See [ROADMAP.md](ROADMAP.md) for the repair
order and [CONTRIBUTING.md](CONTRIBUTING.md) for test expectations.

## Contribute

Start with provider/configuration validation, mocked HTTP behavior, or scheduler
command generation. Report expected and actual behavior, OS/Python version, and
sanitized reproduction steps through [issues](https://github.com/Monotoba/UDDNSUpdater/issues).
Do not share credentials, raw provider errors, or password-bearing URLs.

Licensed under [BSD-2-Clause](LICENSE).
