# Scheduler validation baseline

Daily planning and Linux, macOS, and Windows definition previews are implemented.
Main also provides explicit named install/remove modes; Linux supports cron and
systemd user timers. General schedule() calls remain blocked. Version 0.1.0a2 includes explicit installation; 0.1.0a1
had previews only. Persistent DDNS acceptance/error controls are implemented,
but live evidence varies by provider and scheduler. See [release validation](RELEASE_VALIDATION.md).

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

Do not put DDNS service sections in this file. The separate `[Task1]` format now supports daily planning through
`UTaskScheduler/scheduler.py`, as described below. Dates/calendar restrictions
and installation remain unavailable. The legacy manual is a design draft.

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

1. Linux, macOS, and Windows definition previews are implemented with offline
   tests. Native service acceptance and behavior remain to be validated.
2. The Task-section parser now validates JSON actions and daily schedules through
   the unified API. Multi-task native previews/installation and restricted
   calendar/date features remain unavailable.
3. Validate the implemented persistent DDNS acceptance/error controls with
   disposable provider records where credentials are available.
4. Validate native user-task installation/removal in controlled environments
   before enabling it. Document partial installation, permissions, duplicate
   task handling, local-time behavior, and recovery.

Routine push/PR tests prohibit native task mutations. Separate manual workflows
use disposable hosted-runner tasks and the authorized DuckDNS test record.

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
file. The preview performs no existing-entry preservation or duplicate handling.
Explicit install/remove modes on main are described below; real environment and
execution evidence is tracked in RELEASE_VALIDATION.md.

The [cron manual](https://man7.org/linux/man-pages/man5/crontab.5.html) specifies
that percent characters are processed before the command reaches the shell.
The renderer quotes each argument and isolates escaped percent characters so
literal backslashes before percent remain intact. Tests model cron's escape scan
and also run a harmless argv round trip through /bin/sh on Linux/macOS; the actual
shell check is skipped on Windows. A separate manual Ubuntu 24.04 workflow has
also verified actual cron daemon execution and cleanup.

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

## macOS launchd preview

```sh
python -m UTaskScheduler.utask_scheduler --config-file schedule.ini --preview-launchd -- /absolute/path/to/python /absolute/path/to/job.py
```

This macOS-only CLI mode is mutually exclusive with dry run and cron preview.
It prints one XML plist after validating the complete schedule, without writing
files or invoking launchctl. The definition uses the label
`org.monotoba.uddnsupdater`, literal `ProgramArguments` (no shell), and a
`StartCalendarInterval` array containing every Hour/Minute pair. XML-sensitive
characters are escaped by Python's plist serializer. XML-invalid characters,
NUL/newlines, relative executable paths, and invalid trigger times are rejected.

See Apple's [timed-job documentation](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/ScheduledJobs.html)
and [launchd property-list manual](https://github.com/apple-oss-distributions/launchd/blob/main/man/launchd.plist.5).
The preview is intended as a user-agent definition; system-daemon generation
is unavailable. Working directory, environment, executable existence, user
permissions, login/session lifecycle, sleep/wake and daylight-saving behavior
remain unvalidated. Use absolute paths for job resources. Preview prints command
arguments; keep credentials in protected configuration files.

`scheduler.preview_launchd(command)` returns the XML string. The pure backend
`MacTaskScheduler([hour, minute], command=argv, label="org.example.job")`
provides `render_plist()` and `schedule(dry_run=True)`. `render_plist(intervals=...)`
accepts a nonempty list of daily Hour/Minute pairs. The constructor's existing
second positional `system_task` parameter is retained. Installation and legacy
file-writing methods now raise `LaunchdPreviewError` without side effects.
Tests round-trip plist contents; they do not install jobs or establish live
launchd integration. Explicit main-branch registration is described below;
a separate manual macOS workflow has verified scheduled execution and removal.

## Windows Task Scheduler preview

```powershell
python -m UTaskScheduler.utask_scheduler --config-file schedule.ini --preview-windows --start-date 2026-10-09 -- 'C:\Python\python.exe' 'C:\Jobs\job.py'
```

Use your intended start date, not necessarily the example date. This Windows-only
CLI mode requires an explicit valid YYYY-MM-DD date and is mutually exclusive
with the other preview/dry-run modes. `--start-date` is rejected in other modes.
The preview prints UTF-8 XML after complete validation, without creating files,
calling schtasks, or registering a task. There is one daily CalendarTrigger per
Hour/Minute pair with a full local date/time StartBoundary and DaysInterval=1;
no unintended hourly repetition is added. Schedules over 48 triggers are rejected
instead of being partially rendered or split into multiple tasks.

The definition uses Microsoft's Task Scheduler namespace, separates the executable
Command from Arguments, and serializes arguments using Python's MS C runtime
quoting rules. This supports executables such as Python that follow those rules;
other programs' argument parsers require separate validation. The executable must
be an absolute Windows .exe path (including UNC paths); batch files and relative
paths are rejected. XML-invalid/control characters and all percent characters in
commands are rejected because Task Scheduler supports environment-variable
expansion. XML metacharacters are escaped. No shell is inserted by the renderer;
do not pass shell/interpreter command strings unless that is your deliberate job.

See Microsoft's [daily task example](https://learn.microsoft.com/en-us/windows/win32/taskschd/daily-trigger-example--xml-),
[trigger limits](https://learn.microsoft.com/en-us/windows/win32/taskschd/task-triggers),
and [execution action](https://learn.microsoft.com/en-us/windows/win32/taskschd/execaction).
Identity/logon policy, working directory, environment, executable existence,
permissions, execution/settings defaults, service schema acceptance, and native
sleep/wake/time-zone behavior remain unvalidated. Preview prints arguments; keep
credentials in protected configuration files. This is not an installation guide.

`scheduler.preview_windows(argv, start_date="2026-10-09")` returns XML.
`WindowsTaskScheduler([hour, minute], argv).create_task_xml(start_date=...)`
generates one trigger; `intervals=[[hour, minute], ...]` generates up to 48.
`schedule(dry_run=True, start_date=...)` returns the preview; installation calls
raise WindowsPreviewError. Existing constructor name/description parameters are
retained; the name is validated but registration naming remains external to XML.
Tests inspect the XML and run a harmless real Windows process argv round trip
in routine Windows CI. Actual registration/execution is checked separately by
the manual desktop workflow; consult RELEASE_VALIDATION.md for current results.

## Task-section daily planning

Use `python -m UTaskScheduler.scheduler --config-file tasks.ini --dry-run`.
The direct `UTaskScheduler/scheduler.py` entry point also works outside the repo
with absolute script/configuration paths. This is a separate format from SCHEDULE
and DDNS provider configurations; they cannot be mixed.

```ini
[Task1]
name = Daily example
action = ["python", "-c", "print('Hello World')"]
hours = */6
minutes = */15
days = *
weeks = *
months = *
years = *
```

Section names must be Task followed by a positive decimal integer. Actions are
strict JSON lists of strings, preserving spaces, backslashes, empty arguments,
and percent characters without interpolation. JSON Windows paths require doubled
backslashes. Plain command strings and Python list literals are rejected rather
than guessed; no shell splitting or command execution occurs. Names default to
the section name and must be nonempty and unique ignoring case. Names are planning
labels only, not validated native file paths or registration identifiers.

Hours/minutes use the same validated *, */N, or integer fields as the unified
planner. Legacy defaults remain hours=* and minutes=*/10 (144 daily triggers).
Days/weeks/months/years must be omitted or *; date must be omitted or empty.
Unknown fields, DEFAULT values, mixed formats, duplicate sections/names, missing
files, malformed JSON, and unsupported dates/calendar restrictions fail explicitly.
All tasks are validated before output; dry run reports counts without printing
names or actions. It validates daily planning only, not backend path/trigger limits.
For example Windows XML previews support at most 48 triggers while planning may
represent more. Use absolute executable/resource paths for eventual native jobs.

`parse_config(path)` returns the validated legacy task dictionaries.
`plan_tasks(path)` returns a list of name/triggers dictionaries using the unified
`schedule_task(..., dry_run=True)` API. Neither executes actions nor installs jobs.
Omitting --dry-run returns exit 1 for a valid configuration; invalid configurations
return 2; successful planning returns 0. Multi-task preview output and native
installation remain unavailable. `UTaskScheduler/sample.ini` is a planning example.

## Development toward 1.0: explicit Linux installation

Main now supports explicit `--install-cron NAME` and `--remove-cron NAME` modes.
These modes are included in 0.1.0a2 and affect only
an existing Linux user crontab, never system crontabs or another user's tasks.
Names use 1–64 ASCII letters, digits, underscores or hyphens. Normal schedule()
calls remain blocked; installation requires the explicit CLI mode.

The DDNS task examples below include `--no-log` because native working directories
may not be writable. The probe checks observed the home directory for cron/systemd,
`/` for launchd and `C:\Windows\system32` for Windows. Default DDNS file logging
writes `ddns_update.log` in that working directory; without `--no-log`, confirm it
is writable. Always supply absolute configuration, state and resource paths.

```sh
python -m UTaskScheduler.utask_scheduler --config-file schedule.ini --install-cron ddns -- /absolute/path/to/python /absolute/path/to/ddns_updater.py --config-file /absolute/path/to/ddns.ini --state-file /absolute/path/to/state.json --refresh-seconds 3600 --no-log
python -m UTaskScheduler.utask_scheduler --remove-cron ddns
```

The refresh value is an example, not a verified provider interval. Use absolute
paths and a protected existing state directory. The commands read the existing
crontab, preserve unrelated entries, replace only their named marker block, and
verify the result. Reinstallation is idempotent. Removing a missing block does
not write. A missing/unreadable crontab fails closed: initialize an empty user
crontab yourself first. Unsupported shell settings and malformed duplicate markers
also fail closed. Crontab stderr is withheld, and native commands have a 15-second
timeout. Failures after a write require checking native state before retrying.

Back up your crontab and avoid simultaneous edits: crontab exposes no atomic
compare-and-swap, so concurrent editors can overwrite each other's changes.
Installation is mocked in routine tests. The manual Ubuntu 24.04 check passed
scheduled execution, exact argv, unrelated-entry preservation and restoration.
Other environments and cross-platform integration remain separate gates for 1.0.
Explicit macOS/Windows installation is also implemented on main as described
below. No task is installed by tests or build checks.

## Development toward 1.0: explicit macOS registration

Main now supports `--install-launchd NAME` and `--remove-launchd NAME` for the
current user's `gui/UID` launchd domain. An active GUI login session is required.
Version 0.1.0a2 also implements Windows
registration, described in the following section.

```sh
python -m UTaskScheduler.utask_scheduler --config-file schedule.ini --install-launchd ddns -- /absolute/path/to/python /absolute/path/to/ddns_updater.py --config-file /absolute/path/to/ddns.ini --state-file /absolute/path/to/state.json --refresh-seconds 3600 --no-log
python -m UTaskScheduler.utask_scheduler --remove-launchd ddns
```

Choose the refresh interval for your provider. No native installation occurs
unless you select this explicit mode. Each task has label
org.monotoba.uddnsupdater.NAME and a plist beneath ~/Library/LaunchAgents.
Only daily schedules are supported. Commands preserve argument boundaries and
must start with an absolute executable. No shell interpolation is used.

Installation rejects existing files and registered label collisions, creates the
file exclusively with mode 0600, bootstraps it, and verifies registration.
Remove explicitly before reinstalling. Removal checks a valid matching managed
plist, boots out the label if registered, verifies absence, then deletes that
file. Unknown registration statuses fail closed. Missing/foreign definitions or
symlinks are rejected. Failed registration retains the definition for explicit
recovery; errors after a write may leave partial native state and must be inspected.
Launchctl commands have 15-second timeouts and raw diagnostics are withheld.

Use a trusted home directory; this is not protection against another process
that can modify it or race file/native operations. Avoid concurrent changes to
the same label. Registered service identity is checked by label, not by execution
history. The manual macOS 15 Intel check verified GUI-domain scheduled execution,
exact argv, removal and unrelated plist preservation. Other permission/session,
sleep and missed-trigger behavior remain environment-specific checks. Routine tests
mock launchctl and never register real tasks. No system daemon or elevated installation
is supported.

## Development toward 1.0: explicit Windows registration

Main now supports `--install-windows NAME --start-date YYYY-MM-DD` and
`--remove-windows NAME`. Both are included in 0.1.0a2.
Registration creates a task named UDDNSUpdater-NAME at the local root task path.
It uses the current user's SID, InteractiveToken logon, and LeastPrivilege;
no password, remote account, or elevated principal is requested. The user must
be logged on for execution. Windows task permissions may still prevent registration.

```powershell
python -m UTaskScheduler.utask_scheduler --config-file schedule.ini --install-windows ddns --start-date 2026-10-10 -- C:\Python\python.exe C:\Tools\ddns_updater.py --config-file C:\Private\ddns.ini --state-file C:\Private\state.json --refresh-seconds 3600 --no-log
python -m UTaskScheduler.utask_scheduler --remove-windows ddns
```

Paths, date, and interval are examples; choose them for your environment/provider.
Installation accepts 1–48 daily triggers and the existing absolute .exe/argument
rules. Percent characters remain unsupported because native expansion could
change arguments. Existing names are rejected, with no forced overwrite.
Remove explicitly before reinstalling. Removal requires the managed description
and current-user SID; it verifies that the named task is gone. Registered XML is
checked for expected command, arguments, trigger boundaries, logon type, and run
level. Verification failures can leave a registered task; inspect Task Scheduler
before retrying. Removing a task does not guarantee its running process is stopped.
Principal account names and SID strings are resolved to a SID before ownership
comparison. Native registration independently verifies run level 0 (least
privilege). An omitted RunLevel in exported XML is accepted only with that native
verification; explicit elevated or unverified levels are rejected.

PowerShell runs without a profile or interactive prompts, with a 30-second timeout.
User values arrive as JSON on stdin, not interpolated script code. Raw diagnostics
are withheld. The manual hosted-Windows check verified registration/export,
scheduled execution, exact argv and removal. Other permissions, battery/idle
defaults, login states and missed triggers require environment-specific validation. Automated tests mock task commands; Windows CI
parses the PowerShell syntax without registering tasks. Avoid concurrent edits of
the same name. No system, remote, password-based, or elevated tasks are supported.

## Linux choice: cron or systemd user timers

On main, choose the Linux backend explicitly. Existing `--install-cron`,
`--remove-cron` and `--preview-cron` commands continue to work. Generic modes
require `--scheduler cron` or `--scheduler systemd`:

```sh
python -m UTaskScheduler.utask_scheduler --config-file schedule.ini --scheduler systemd --preview ddns -- /absolute/path/to/python -m ddns_updater --config-file /absolute/path/to/ddns.ini --state-file /absolute/path/to/state.json --refresh-seconds 3600 --no-log
python -m UTaskScheduler.utask_scheduler --config-file schedule.ini --scheduler systemd --install ddns -- /absolute/path/to/python -m ddns_updater --config-file /absolute/path/to/ddns.ini --state-file /absolute/path/to/state.json --refresh-seconds 3600 --no-log
python -m UTaskScheduler.utask_scheduler --scheduler systemd --status ddns
python -m UTaskScheduler.utask_scheduler --scheduler systemd --remove ddns
```

Choose the refresh interval for your provider. Substitute `cron` to use a named
user-crontab block. Cron status checks marker presence only, not daemon health or
execution. Systemd-specific aliases are `--preview-systemd NAME`,
`--install-systemd NAME`, `--status-systemd NAME`, and `--remove-systemd NAME`.
Remove/status need no schedule configuration and accept no command. Do not install
the same updater through both backends unless that is intentional.

Systemd uses the same local daily Hour/Minute Cartesian product (up to 1,440
triggers). It writes `uddnsupdater-NAME.service` and `.timer` beneath
`$XDG_CONFIG_HOME/systemd/user`, defaulting to `~/.config/systemd/user`. Preview
prints both definitions, labeled by filename, with no files or subprocesses.
The Python API `scheduler.preview_systemd(argv, name)` returns a filename/text
mapping. No root, system-wide unit, sudo, credential prompt or automatic backend
fallback is used. An existing user systemd manager and accessible user bus are
required; a missing manager fails before definitions are created.

The service is Type=oneshot, works from the user's home directory, and uses
UMask=0077. ExecStart uses systemd quoting, escapes percent specifiers, and
suppresses dollar-variable substitution with its `:` prefix; no shell is added.
Empty arguments, literal dollar/percent strings, quotes, backslashes and semicolons
are preserved. Executables must be absolute; arguments must be valid UTF-8 without
control characters. Use absolute paths for all resources and keep credentials in
protected configuration files. Preview and unit metadata contain argv verbatim.

Timers use OnCalendar, AccuracySec=1s, no randomized delay, and Persistent=false.
They do not replay missed runs on activation or wake a suspended computer. Timer
accuracy is not a real-time execution guarantee. Jobs longer than their interval
are not started again while the same oneshot service is active. Clock/time-zone,
DST, reboot and suspend behavior require testing in the intended environment.
Calendar triggers elapsed while sleeping may coalesce into one run on resume;
Persistent=false concerns time while the timer is inactive, not sleep catch-up.

A user manager generally follows login/session lifetime. Running without an active
login may require an administrator-authorized `loginctl enable-linger USER`; inspect
`loginctl show-user USER -p Linger` first. This tool never changes linger. See the
upstream [timer manual](https://github.com/systemd/systemd/blob/main/man/systemd.timer.xml),
[service command syntax](https://github.com/systemd/systemd/blob/main/man/systemd.service.xml),
[quoting rules](https://github.com/systemd/systemd/blob/main/man/systemd.syntax.xml),
and [loginctl manual](https://www.freedesktop.org/software/systemd/man/252/loginctl.html).

Install refuses existing unit files, registered names, enablement links, symlinks
and drop-ins. It creates files exclusively with mode 0600, reloads the user manager,
verifies native fragment identity, and enables/starts only the timer. Remove before
reinstalling. Status verifies unchanged managed files and reports LoadState,
ActiveState and UnitFileState for both units; it does not claim a successful job run.
For execution diagnostics, use `journalctl --user -u uddnsupdater-NAME.service`
and `systemctl --user list-timers uddnsupdater-NAME.timer`.

Removal accepts only unchanged current-user managed definitions, checks native
fragment paths/drop-ins, disables/stops the timer, stops its service (including a
running job), removes managed files, reloads and verifies absence. Partial pairs
from an ordinary failed install can be removed when their surviving definitions
are valid. Edited/foreign or truncated files require manual inspection; they are
never silently overwritten or deleted. Errors after writes or native changes can
leave partial state; inspect before retrying. Native commands have 30-second
timeouts and fixed diagnostics. Use trusted nonsymlink parent directories and
avoid concurrent edits: file/native operations are not an atomic transaction.

Routine tests use mocked user-manager operations plus systemd-analyze verification
on Linux. The separate manual workflow checks actual scheduled execution and
cleanup. Consult RELEASE_VALIDATION.md for evidence before unattended use.
