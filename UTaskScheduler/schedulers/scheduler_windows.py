import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET

class WindowsTaskScheduler:
    def __init__(self, schedule_args, command, task_name="MyTask", task_description="Scheduled Task"):
        self.schedule_args = schedule_args
        self.command = command
        self.task_name = task_name
        self.task_description = task_description

    def schedule(self):
        # Create an XML task definition for Windows Task Scheduler
        task_xml = self.create_task_xml()

        # Generate a temporary XML file for the task definition
        temp_dir = tempfile.gettempdir()
        task_file_path = os.path.join(temp_dir, f"{self.task_name}_task.xml")

        with open(task_file_path, "w") as task_file:
            task_file.write(task_xml)

        # Use schtasks to create the scheduled task
        try:
            task_command = f"schtasks /CREATE /XML {task_file_path} /TN {self.task_name}"
            subprocess.run(task_command, shell=True, check=True)
            print(f"Task '{self.task_name}' scheduled successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Error: {e}")
        finally:
            # Clean up the temporary XML file
            os.remove(task_file_path)

    def create_task_xml(self):
        # Create an XML task definition for Windows Task Scheduler
        task_name = self.task_name
        task_description = self.task_description
        task_command = self.command

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
