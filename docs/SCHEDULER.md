# Scheduler validation baseline

Daily planning and Linux user-crontab previews are implemented, with no native
task installation. The Linux backend now also blocks direct installation calls.
macOS and Windows backends still need repair; their direct APIs must not be used
to install tasks. DDNS providers lack persistent change/error controls required
for unattended use.

## Configuration

Use a separate UTF-8 file containing only `[SCHEDULE]`:

```ini
[SCHEDULE]
Hour = *
Minute = */15
```

Hour is 0–23 and Minute is 0–59. Supported field forms are `*`, `*/N`, and a single
integer. Steps must be positive and at most the field's size. Ranges, comma lists,
years, dates, day/week/month selectors, and other keys are rejected rather than
silently ignored. Missing Hour or Minute defaults to 0, so an empty SCHEDULE
section plans one daily trigger at midnight. Hours and minutes form a Cartesian
product: `Hour=*/6` and `Minute=*/15` produce 16 daily trigger times. These are
local calendar times, not elapsed-time intervals or one-time dates. Native time
zone/daylight-saving behavior remains unvalidated.

Do not put DDNS service sections in this file. The older `[Task1]` action/date
format and `UTaskScheduler/scheduler.py` task installer remain unfinished. The
legacy manual is a design draft, not an operating guide.

## Dry run

From the repository root, with dependencies installed:

```sh
python -m UTaskScheduler.utask_scheduler --config-file schedule.ini --dry-run -- /absolute/path/to/python /absolute/path/to/job.py
```

The direct script entry point also works from other directories; supply absolute
paths to the script and configuration. A successful run reports the number of
validated triggers without printing the command. It creates no files and runs
no native scheduling tool. The command after `--` is an argument list; quote paths
or individual arguments containing spaces as appropriate for your shell. No
joining into a shell command occurs during planning. Literal `%` values are
preserved. Empty arguments are allowed after the executable; NUL/newline arguments
and an empty executable are rejected.

Exit 0 means a valid dry run. Invalid configuration, command, or unsupported OS
returns 2. Omitting `--dry-run` on a valid configuration returns 1 with an explicit
installation-unavailable error; no task is installed. Linux, Windows, and Darwin
are recognized for planning; this does not establish working native integration.

## Python API

```python
from UTaskScheduler.utask_scheduler import UTaskScheduler

scheduler = UTaskScheduler("schedule.ini")
triggers = scheduler.schedule(["/absolute/path/to/python", "/absolute/path/to/job.py"], dry_run=True)
# Each trigger has platform, action (argument list), hour, and minute.
```

`plan(command)` provides the same validation and trigger list. Pass a list or
tuple of strings; raw command strings are rejected to preserve argument boundaries.
`schedule_task(command, hour, minute, dry_run=True)` validates a single trigger.
Unified API installation calls raise `SchedulerUnavailableError` before any native action.
Configuration failures raise `SchedulerError` without echoing file contents or
command arguments.

## Remaining repair order

1. Linux user-crontab generation and preview are implemented. Repair macOS
   launchd and Windows Task Scheduler definitions next, with offline tests.
2. Reconcile the older Task-section parser, names, paths, and unsupported date/
   calendar features with the unified API; add complete upfront validation.
3. Add persistent DDNS change detection and provider error/cooldown controls.
4. Validate native user-task installation/removal in controlled environments
   before enabling it. Document partial installation, permissions, duplicate
   task handling, local-time behavior, and recovery.

Tests prohibit native task mutations. No live task installation or DNS updates
were performed for this baseline.

## Linux user-crontab preview

```sh
python -m UTaskScheduler.utask_scheduler --config-file schedule.ini --preview-cron -- /absolute/path/to/python /absolute/path/to/job.py
```

`--preview-cron` and `--dry-run` are mutually exclusive. Preview validates the
complete configuration first and prints a definition only after all entries have
been generated. It does not read, replace, or append to a user's crontab, create
files, or run subprocesses. This mode requires a Linux schedule and an absolute
executable path; argument paths and executable existence are not checked. Use
absolute paths for the script, DDNS configuration, and other job resources because
a cron job's working directory and environment differ from an interactive shell.

The output starts with `SHELL=/bin/sh` and contains one five-field daily entry
per trigger, with a final newline. It is a user-crontab snippet, not a system
crontab (which requires a username), and not a replacement for an existing full
crontab. A SHELL setting affects subsequent entries when combined with an existing
file. Existing-entry preservation, duplicate handling, environment integration,
and native installation/removal are not implemented.

The [cron manual](https://man7.org/linux/man-pages/man5/crontab.5.html) specifies
that percent characters are processed before the command reaches the shell.
The renderer quotes each argument and isolates escaped percent characters so
literal backslashes before percent remain intact. Tests model cron's escape scan
and also run a harmless argv round trip through /bin/sh on Linux/macOS; the actual
shell check is skipped on Windows. No cron daemon was installed or invoked.

Unlike the ordinary dry run, this explicit preview prints command arguments.
Keep credentials in protected configuration files rather than command arguments.
Normal installation is still blocked; the preview does not establish readiness
for unattended DDNS updates or validate native scheduling behavior.

The Python API `scheduler.preview_cron(command)` returns this definition.
`UnixTaskScheduler([hour, minute], command).render_cron()` generates one daily
entry; `render_cron_line()` returns its entry without the header/newline. The
backend's `schedule(dry_run=True)` and `schedule_linux(dry_run=True)` return a
preview. Calls without dry_run raise CronPreviewError; system-task generation
is explicitly unavailable. Arguments must be a list or tuple, not a shell string.
