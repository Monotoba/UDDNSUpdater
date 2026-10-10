import argparse
import configparser
import sys


class SchedulerError(RuntimeError):
    """Controlled scheduling configuration or availability error."""


class SchedulerUnavailableError(SchedulerError):
    """Native installation is deliberately unavailable during backend repair."""


class UTaskScheduler:
    def __init__(self, config_file="config.ini"):
        self.config_file = config_file

    def plan(self, command):
        """Validate the complete schedule and return daily triggers without writes."""
        command = self.validate_command(command)
        config = configparser.ConfigParser(interpolation=None)
        try:
            with open(self.config_file, encoding="utf-8") as handle:
                config.read_file(handle)
        except (OSError, UnicodeError, configparser.Error):
            raise SchedulerError("Cannot read a valid UTF-8 scheduler configuration.") from None
        if config.sections() != ["SCHEDULE"]:
            raise SchedulerError("Scheduler configuration must contain only [SCHEDULE].")
        settings = config["SCHEDULE"]
        if set(settings) - {"hour", "minute"}:
            raise SchedulerError("Unsupported scheduler configuration field.")
        hours = self.parse_cron_field(settings.get("hour", "0"), 24)
        minutes = self.parse_cron_field(settings.get("minute", "0"), 60)
        return [self.schedule_task(command, hour, minute, dry_run=True)
                for hour in hours for minute in minutes]

    def preview_cron(self, command):
        """Render the full validated Linux schedule without reading a crontab."""
        tasks = self.plan(command)
        if tasks[0]['platform'] != 'Linux':
            raise SchedulerError('Cron preview is available only for Linux schedules.')
        if __package__:
            from .schedulers.scheduler_unix import UnixTaskScheduler, CronPreviewError
        else:
            from schedulers.scheduler_unix import UnixTaskScheduler, CronPreviewError
        try:
            lines = [UnixTaskScheduler([task['hour'], task['minute']], task['action']).render_cron_line()
                     for task in tasks]
        except CronPreviewError as error:
            raise SchedulerError(str(error)) from None
        return 'SHELL=/bin/sh\n' + '\n'.join(lines) + '\n'

    def preview_launchd(self, command):
        """Render one user-agent plist with all daily triggers, without writes."""
        tasks = self.plan(command)
        if tasks[0]['platform'] != 'Darwin':
            raise SchedulerError('Launchd preview is available only for macOS schedules.')
        if __package__:
            from .schedulers.scheduler_macos import MacTaskScheduler, LaunchdPreviewError
        else:
            from schedulers.scheduler_macos import MacTaskScheduler, LaunchdPreviewError
        try:
            return MacTaskScheduler([tasks[0]['hour'], tasks[0]['minute']], command=tasks[0]['action']).render_plist(
                intervals=[[task['hour'], task['minute']] for task in tasks])
        except LaunchdPreviewError as error:
            raise SchedulerError(str(error)) from None

    def preview_windows(self, command, *, start_date=None):
        """Render a Windows task definition without native registration."""
        tasks = self.plan(command)
        if tasks[0]['platform'] != 'Windows':
            raise SchedulerError('Windows preview is available only for Windows schedules.')
        if __package__:
            from .schedulers.scheduler_windows import WindowsTaskScheduler, WindowsPreviewError
        else:
            from schedulers.scheduler_windows import WindowsTaskScheduler, WindowsPreviewError
        try:
            return WindowsTaskScheduler([tasks[0]['hour'], tasks[0]['minute']], tasks[0]['action']).create_task_xml(
                start_date=start_date, intervals=[[task['hour'], task['minute']] for task in tasks])
        except WindowsPreviewError as error:
            raise SchedulerError(str(error)) from None

    def preview_systemd(self, command, name):
        """Return named user service/timer definitions without files or subprocesses."""
        tasks = self.plan(command)
        if tasks[0]['platform'] != 'Linux':
            raise SchedulerError('Systemd preview is available only for Linux schedules.')
        if __package__:
            from .schedulers.scheduler_systemd import render_units, SystemdError
        else:
            from schedulers.scheduler_systemd import render_units, SystemdError
        try:
            return render_units(name, tasks[0]['action'],
                                [[task['hour'], task['minute']] for task in tasks])
        except SystemdError as error:
            raise SchedulerError(str(error)) from None

    def schedule(self, command, *, dry_run=False):
        tasks = self.plan(command)
        if dry_run:
            return tasks
        # Definition previews do not establish safe native installation.
        raise SchedulerUnavailableError("Native task installation is unavailable; use --dry-run.")

    def schedule_task(self, command, hour, minute, *, dry_run=False):
        command = self.validate_command(command)
        if (type(hour) is not int or type(minute) is not int
                or not 0 <= hour < 24 or not 0 <= minute < 60):
            raise SchedulerError("Invalid daily trigger time.")
        system = {"win32": "Windows", "linux": "Linux", "darwin": "Darwin"}.get(sys.platform)
        if system not in {"Windows", "Linux", "Darwin"}:
            raise SchedulerError("Unsupported operating system for task scheduling.")
        if not dry_run:
            raise SchedulerUnavailableError("Native task installation is unavailable; use --dry-run.")
        return {"platform": system, "action": command, "hour": hour, "minute": minute}

    @staticmethod
    def validate_command(command):
        # Keep argument boundaries, rather than joining and invoking a shell.
        if (not isinstance(command, (list, tuple)) or not command
                or not isinstance(command[0], str) or not command[0].strip()
                or any(not isinstance(arg, str) or any(c in arg for c in "\x00\r\n")
                       for arg in command)):
            raise SchedulerError("Task command must be a nonempty argument list.")
        return list(command)

    @staticmethod
    def parse_cron_field(field, max_value):
        if not isinstance(field, str) or type(max_value) is not int or max_value <= 0:
            raise SchedulerError("Invalid schedule field.")
        field = field.strip()
        if len(field) > 64:
            raise SchedulerError("Schedule field is too long.")
        if field == "*":
            return list(range(max_value))
        if field.startswith("*/") and field[2:].isascii() and field[2:].isdigit():
            interval = int(field[2:])
            if 1 <= interval <= max_value:
                return list(range(0, max_value, interval))
        elif field.isascii() and field.isdigit():
            value = int(field)
            if 0 <= value < max_value:
                return [value]
        raise SchedulerError("Invalid schedule field; use *, */N, or an in-range integer.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate a daily native task schedule")
    parser.add_argument("--config-file", default="config.ini")
    parser.add_argument('--scheduler', choices=['cron', 'systemd'], help='Explicit Linux backend for generic modes')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--preview', metavar='NAME', help='Preview a named Linux task using --scheduler')
    mode.add_argument('--install', metavar='NAME', help='Install a named Linux task using --scheduler')
    mode.add_argument('--remove', metavar='NAME', help='Remove a named Linux task using --scheduler')
    mode.add_argument('--status', metavar='NAME', help='Inspect a named Linux task using --scheduler')
    mode.add_argument('--preview-systemd', metavar='NAME', help='Print named systemd user service/timer definitions')
    mode.add_argument('--install-systemd', metavar='NAME', help='Explicitly enable/start a named systemd user timer')
    mode.add_argument('--remove-systemd', metavar='NAME', help='Stop/remove managed systemd user units')
    mode.add_argument('--status-systemd', metavar='NAME', help='Inspect managed systemd user unit state')
    mode.add_argument('--status-cron', metavar='NAME', help='Inspect named user-crontab block presence')
    mode.add_argument("--install-windows", metavar="NAME", help="Explicitly register a current-user Windows task")
    mode.add_argument("--remove-windows", metavar="NAME", help="Remove a managed current-user Windows task")
    mode.add_argument("--install-launchd", metavar="NAME", help="Explicitly register a named macOS user agent")
    mode.add_argument("--remove-launchd", metavar="NAME", help="Remove only a named macOS user agent")
    mode.add_argument("--install-cron", metavar="NAME", help="Explicitly install/replace a named Linux user-crontab block")
    mode.add_argument("--remove-cron", metavar="NAME", help="Remove only a named Linux user-crontab block")
    mode.add_argument("--dry-run", action="store_true", help="Validate only; no native task installation")
    mode.add_argument("--preview-cron", action="store_true", help="Print Linux user-crontab definition without installation")
    mode.add_argument("--preview-launchd", action="store_true", help="Print macOS user-agent plist without installation")
    mode.add_argument("--preview-windows", action="store_true", help="Print Windows task XML without registration")
    parser.add_argument("--start-date", help="Windows preview start date (YYYY-MM-DD)")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Argument list after --")
    args = parser.parse_args(argv)
    generic = next((operation for operation in ('preview', 'install', 'remove', 'status')
                    if getattr(args, operation) is not None), None)
    if bool(generic) != bool(args.scheduler):
        parser.error('--scheduler requires --preview, --install, --remove, or --status, and vice versa')
    if generic:
        value = getattr(args, generic)
        if args.scheduler == 'cron' and generic == 'preview':
            if __package__:
                from .schedulers.cron_install import markers
                from .schedulers.scheduler_unix import CronPreviewError
            else:
                from schedulers.cron_install import markers
                from schedulers.scheduler_unix import CronPreviewError
            try:
                markers(value)
            except CronPreviewError as error:
                parser.error(str(error))
            args.preview_cron = True
        else:
            setattr(args, generic + '_' + args.scheduler, value)
    if args.start_date is not None and not (args.preview_windows or args.install_windows is not None):
        parser.error("--start-date requires --preview-windows or --install-windows")
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    try:
        scheduler = UTaskScheduler(args.config_file)
        if any(getattr(args, operation + '_systemd') is not None
               for operation in ('preview', 'install', 'remove', 'status')):
            if sys.platform != 'linux':
                raise SchedulerError('Systemd operations are available only on Linux.')
            if (args.remove_systemd is not None or args.status_systemd is not None) and command:
                raise SchedulerError('Systemd remove/status does not accept a command.')
            if __package__:
                from .schedulers.systemd_install import install, remove, status
                from .schedulers.scheduler_systemd import SystemdError
            else:
                from schedulers.systemd_install import install, remove, status
                from schedulers.scheduler_systemd import SystemdError
            try:
                if args.preview_systemd is not None:
                    units = scheduler.preview_systemd(command, args.preview_systemd)
                    for filename, text in units.items():
                        print('# File: ' + filename + '\n' + text, end='')
                elif args.install_systemd is not None:
                    tasks = scheduler.plan(command)
                    install(args.install_systemd, tasks[0]['action'],
                            [[task['hour'], task['minute']] for task in tasks])
                    print('Named systemd user timer activation verified.')
                elif args.remove_systemd is not None:
                    remove(args.remove_systemd)
                    print('Named systemd user units removed and absence verified.')
                else:
                    import json
                    print(json.dumps(status(args.status_systemd), sort_keys=True))
            except SystemdError as error:
                raise SchedulerError(str(error)) from None
            return 0
        if args.status_cron is not None:
            if sys.platform != 'linux' or command:
                raise SchedulerError('Cron status requires Linux and accepts no command.')
            if __package__:
                from .schedulers.cron_install import status
                from .schedulers.scheduler_unix import CronPreviewError
            else:
                from schedulers.cron_install import status
                from schedulers.scheduler_unix import CronPreviewError
            try:
                print('Named user-crontab block: ' + ('present' if status(args.status_cron) else 'absent'))
            except CronPreviewError as error:
                raise SchedulerError(str(error)) from None
            return 0
        if args.install_windows is not None or args.remove_windows is not None:
            if sys.platform != 'win32':
                raise SchedulerError('Native Windows operations are available only on Windows.')
            if args.remove_windows is not None and command:
                raise SchedulerError('Remove-windows does not accept a command.')
            if __package__:
                from .schedulers.windows_install import install, remove
                from .schedulers.scheduler_windows import WindowsPreviewError
            else:
                from schedulers.windows_install import install, remove
                from schedulers.scheduler_windows import WindowsPreviewError
            try:
                if args.install_windows is not None:
                    tasks = scheduler.plan(command)
                    install(args.install_windows, tasks[0]['action'],
                            [[task['hour'], task['minute']] for task in tasks], args.start_date)
                else:
                    remove(args.remove_windows)
            except WindowsPreviewError as error:
                raise SchedulerError(str(error)) from None
            print('Named Windows task operation verified.')
            return 0
        if args.install_launchd is not None or args.remove_launchd is not None:
            if sys.platform != 'darwin':
                raise SchedulerError('Native launchd operations are available only on macOS.')
            if args.remove_launchd is not None and command:
                raise SchedulerError('Remove-launchd does not accept a command.')
            if __package__:
                from .schedulers.launchd_install import install, remove
                from .schedulers.scheduler_macos import LaunchdPreviewError
            else:
                from schedulers.launchd_install import install, remove
                from schedulers.scheduler_macos import LaunchdPreviewError
            try:
                if args.install_launchd is not None:
                    tasks = scheduler.plan(command)
                    install(args.install_launchd, tasks[0]['action'],
                            [[task['hour'], task['minute']] for task in tasks])
                else:
                    remove(args.remove_launchd)
            except LaunchdPreviewError as error:
                raise SchedulerError(str(error)) from None
            print('Named user-agent operation verified.')
            return 0
        if args.install_cron is not None or args.remove_cron is not None:
            if sys.platform != 'linux':
                raise SchedulerError('Native cron operations are available only on Linux.')
            if args.remove_cron is not None and command:
                raise SchedulerError('Remove-cron does not accept a command.')
            if __package__:
                from .schedulers.cron_install import apply
                from .schedulers.scheduler_unix import CronPreviewError
            else:
                from schedulers.cron_install import apply
                from schedulers.scheduler_unix import CronPreviewError
            try:
                apply(args.install_cron or args.remove_cron,
                      scheduler.preview_cron(command) if args.install_cron is not None else None)
            except CronPreviewError as error:
                raise SchedulerError(str(error)) from None
            print('Named user-crontab operation verified.')
            return 0
        if args.preview_cron:
            preview = scheduler.preview_cron(command)
        elif args.preview_launchd:
            preview = scheduler.preview_launchd(command)
        elif args.preview_windows:
            preview = scheduler.preview_windows(command, start_date=args.start_date)
        else:
            tasks = scheduler.schedule(command, dry_run=args.dry_run)
    except SchedulerUnavailableError as error:
        print(str(error), file=sys.stderr)
        return 1
    except SchedulerError as error:
        print(str(error), file=sys.stderr)
        return 2
    if args.preview_cron or args.preview_launchd or args.preview_windows:
        print(preview, end="")
    else:
        print(f"Validated {len(tasks)} daily trigger(s). No tasks installed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
