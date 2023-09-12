import configparser
import platform
import sys

from UTaskScheduler.scheduler.scheduler_macos import MacTaskScheduler
from UTaskScheduler.scheduler.scheduler_unix import UnixTaskScheduler
from UTaskScheduler.scheduler.scheduler_windows import WindowsTaskScheduler


class UTaskScheduler:
    def __init__(self, config_file="config.ini"):
        self.config_file = config_file

    def schedule(self, command):
        config = configparser.ConfigParser()
        config.read(self.config_file)

        if "SCHEDULE" in config:
            hour_field = config["SCHEDULE"].get("Hour", "0")
            minute_field = config["SCHEDULE"].get("Minute", "0")

            # Parse cron-like fields with support for */15 and similar intervals
            hours = self.parse_cron_field(hour_field, 24)
            minutes = self.parse_cron_field(minute_field, 60)

            if hours and minutes:
                # Schedule the task based on the parameters
                for hour in hours:
                    for minute in minutes:
                        scheduler = self.get_scheduler(schedule_args=[hour, minute], system_task=True)
                        scheduler.schedule(command)
                print("Scheduled task based on config.ini.")
            else:
                print("Invalid scheduling parameters in config.ini.")
        else:
            print("No scheduling parameters found in config.ini.")

    def get_scheduler(self, schedule_args, system_task=False):
        system = platform.system()
        if system == "Windows":
            return WindowsTaskScheduler(schedule_args, system_task)
        elif system == "Linux":
            return UnixTaskScheduler(schedule_args, system_task)
        elif system == "Darwin":
            return MacTaskScheduler(schedule_args, system_task)
        else:
            print("Unsupported operating system. Task scheduling not available.")
            sys.exit(1)

    def parse_cron_field(self, field, max_value):
        if field == "*":
            return list(range(0, max_value))
        elif "/" in field:
            parts = field.split("/")
            if len(parts) == 2 and parts[0] == "*" and parts[1].isdigit():
                interval = int(parts[1])
                return list(range(0, max_value, interval))
        elif field.isdigit():
            value = int(field)
            if 0 <= value < max_value:
                return [value]
        return []
