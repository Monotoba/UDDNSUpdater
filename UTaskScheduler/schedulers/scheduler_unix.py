import os
import platform
import subprocess


class UnixTaskScheduler:
    def __init__(self, schedule_args, system_task=False):
        self.schedule_args = schedule_args
        self.system_task = system_task

    def update_ddns(self):
        print("Updating DDNS...")
        # Replace this with the command to run ddns_updater.py
        # Example: subprocess.run(["python", "ddns_updater.py", "--arg1", "--arg2"])
        subprocess.run(["python", "ddns_updater.py"])

    def schedule(self):
        system = platform.system()
        if system == "Linux":
            self.schedule_linux()
        elif system == "Darwin":
            self.schedule_macos()
        else:
            print("Unsupported operating system. DDNS scheduling not available.")

    def schedule_linux(self):
        cron_schedule = " ".join(map(str, self.schedule_args))
        cron_command = f"python ddns_updater.py --schedule {cron_schedule}"

        # Write the cron job to the user's crontab
        try:
            username = os.getlogin()
            cron_command = f"(crontab -l 2>/dev/null; echo '{cron_schedule} {cron_command}') | crontab -"
            subprocess.run(cron_command, shell=True, check=True, stdout=subprocess.PIPE)
            print("Cron job scheduled successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Error: {e}")

    def schedule_macos(self):
        print("macOS does not support scheduling tasks via cron directly.")
        print("Consider using launchd or a third-party scheduler on macOS.")
