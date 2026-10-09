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
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Validate only; no native task installation")
    mode.add_argument("--preview-cron", action="store_true", help="Print Linux user-crontab definition without installation")
    mode.add_argument("--preview-launchd", action="store_true", help="Print macOS user-agent plist without installation")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Argument list after --")
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    try:
        scheduler = UTaskScheduler(args.config_file)
        if args.preview_cron:
            preview = scheduler.preview_cron(command)
        elif args.preview_launchd:
            preview = scheduler.preview_launchd(command)
        else:
            tasks = scheduler.schedule(command, dry_run=args.dry_run)
    except SchedulerUnavailableError as error:
        print(str(error), file=sys.stderr)
        return 1
    except SchedulerError as error:
        print(str(error), file=sys.stderr)
        return 2
    if args.preview_cron or args.preview_launchd:
        print(preview, end="")
    else:
        print(f"Validated {len(tasks)} daily trigger(s). No tasks installed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
