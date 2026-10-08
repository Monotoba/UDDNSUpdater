# Contributing

Create a Python 3.10+ virtual environment, install `requirements-dev.txt`, and run
`python -m pytest -q`. CI runs Python 3.10 and 3.12 on Linux, Windows, and Intel
macOS. This baseline checks imports/discovery, help launchers, configuration validation,
dry-run side effects, literal credentials, sanitized output, and raised runtime
failures, shared IPv4 discovery, and the repaired adapters request/response checks.
It does not prove live provider APIs or native scheduling work.

Refactor existing modules in small patches. Add regression tests for every code
change. Mock HTTP requests and scheduler subprocesses; never use real credentials,
change DNS, or install tasks from tests/CI. Keep sensitive data out of commits
and reports. Follow [ROADMAP.md](ROADMAP.md) and update docs as behavior changes.
