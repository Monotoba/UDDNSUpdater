import os

class MacTaskScheduler:
    def __init__(self, schedule_args, system_task=False):
        self.schedule_args = schedule_args
        self.system_task = system_task

    def schedule(self):
        cron_schedule = " ".join(map(str, self.schedule_args))
        cron_command = f"python ddns_updater.py --schedule {cron_schedule}"

        if self.system_task:
            self.create_system_task(cron_schedule, cron_command)
        else:
            self.create_user_task(cron_schedule, cron_command)

    def create_system_task(self, cron_schedule, cron_command):
        plist_file_path = "/Library/LaunchDaemons/com.example.mytask.plist"
        self.write_plist_file(plist_file_path, cron_schedule, cron_command)
        os.system(f"launchctl load {plist_file_path}")

    def create_user_task(self, cron_schedule, cron_command):
        plist_file_path = os.path.expanduser("~/Library/LaunchAgents/com.example.mytask.plist")
        self.write_plist_file(plist_file_path, cron_schedule, cron_command)
        os.system(f"launchctl load {plist_file_path}")

    def write_plist_file(self, plist_file_path, cron_schedule, cron_command):
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.example.mytask</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>{cron_command}</string>
    </array>
    <key>StartCalendarInterval</key>
    <array>
        <dict>
            <key>Hour</key>
            <integer>{self.schedule_args[0]}</integer>
            <key>Minute</key>
            <integer>{self.schedule_args[1]}</integer>
        </dict>
    </array>
</dict>
</plist>
"""
        with open(plist_file_path, "w") as plist_file:
            plist_file.write(plist_content)
            print(f"Created .plist file: {plist_file_path}")
