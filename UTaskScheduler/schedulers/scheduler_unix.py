import os
import subprocess
import platform


class UnixTaskScheduler:
    def __init__(self, schedule_args, command, system_task=False):
        self.schedule_args = schedule_args
        self.command = command
        self.system_task = system_task

    def schedule(self):
        system = platform.system()
        if system == "Linux":
            self.schedule_linux()
        elif system == "Darwin":
            self.schedule_macos()
        else:
            print("Unsupported operating system. Task scheduling not available.")

    def schedule_linux(self):
        cron_schedule = " ".join(map(str, self.schedule_args))

        # Construct the cron command with the specified command
        cron_command = f"{cron_schedule} {self.command}"

        try:
            username = os.getlogin()
            # Schedule the cron job in the user's crontab
            cron_command = f"(crontab -l 2>/dev/null; echo '{cron_command}') | crontab -"
            subprocess.run(cron_command, shell=True, check=True, stdout=subprocess.PIPE)
            print("Cron job scheduled successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Error: {e}")

    def schedule_macos(self):
        print("macOS does not support scheduling tasks via cron directly.")
        print("Consider using launchd or a third-party scheduler on macOS.")
