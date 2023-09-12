import getpass
import os
import subprocess
import tempfile


class WindowsTaskScheduler:
    def __init__(self, schedule_args, system_task=False):
        self.schedule_args = schedule_args
        self.system_task = system_task

    def schedule(self):
        # Create an XML task definition for Windows Task Scheduler
        task_xml = self.create_task_xml()

        # Determine the task folder (system or user)
        task_folder = "\\Microsoft\\Windows\\DDNSScheduler" if self.system_task else ""

        # Generate a temporary XML file for the task definition
        temp_dir = tempfile.gettempdir()
        task_file_path = os.path.join(temp_dir, "ddns_task.xml")

        with open(task_file_path, "w") as task_file:
            task_file.write(task_xml)

        # Use schtasks to create the scheduled task
        try:
            username = getpass.getuser()
            task_folder = task_folder.replace("\\", "\\\\")
            task_name = "DDNSScheduler"
            task_command = f"schtasks /CREATE /XML {task_file_path} /TN {task_folder}\\{task_name}"
            subprocess.run(task_command, shell=True, check=True)
            print(f"Task '{task_name}' scheduled successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Error: {e}")
        finally:
            # Clean up the temporary XML file
            os.remove(task_file_path)

    def create_task_xml(self):
        # Create an XML task definition for Windows Task Scheduler
        task_name = "DDNSScheduler"
        task_description = "Scheduled task for DDNS updates"
        task_command = "python ddns_updater.py"

        root = ET.Element("Task")
        root.set("version", "1.4")
        registration_info = ET.SubElement(root, "RegistrationInfo")
        ET.SubElement(registration_info, "Description").text = task_description
        triggers = ET.SubElement(root, "Triggers")
        daily_trigger = ET.SubElement(triggers, "CalendarTrigger")
        daily_trigger.set("id", "0")
        start_time = ET.SubElement(daily_trigger, "StartBoundary")
        start_time.text = f"{self.schedule_args[0]:02d}:{self.schedule_args[1]:02d}:00"
        recurrence = ET.SubElement(daily_trigger, "Repetition")
        ET.SubElement(recurrence, "Interval").text = "PT1H"  # Hourly recurrence
        actions = ET.SubElement(root, "Actions")
        exec_action = ET.SubElement(actions, "Exec")
        ET.SubElement(exec_action, "Command").text = task_command

        return ET.tostring(root, encoding="utf-16", method="xml").decode()
