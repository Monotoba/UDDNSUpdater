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

    def schedule(self, command, *, dry_run=False):
        tasks = self.plan(command)
        if dry_run:
            return tasks
        # The native backends remain incompatible and have unvalidated commands.
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
    parser.add_argument("--dry-run", action="store_true", help="Validate only; no native task installation")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Argument list after --")
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    try:
        tasks = UTaskScheduler(args.config_file).schedule(command, dry_run=args.dry_run)
    except SchedulerUnavailableError as error:
        print(str(error), file=sys.stderr)
        return 1
    except SchedulerError as error:
        print(str(error), file=sys.stderr)
        return 2
    print(f"Validated {len(tasks)} daily trigger(s). No tasks installed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
