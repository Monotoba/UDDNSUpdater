"""Windows task XML previews; native registration remains unavailable."""
from datetime import date
from pathlib import PureWindowsPath
import re
import subprocess
import xml.etree.ElementTree as ET

NAMESPACE = 'http://schemas.microsoft.com/windows/2004/02/mit/task'


class WindowsPreviewError(ValueError):
    """Controlled task definition or installation error."""


def xml_safe(value):
    return (isinstance(value, str)
            and not any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF
                        or ord(c) in (0xFFFE, 0xFFFF) for c in value))


class WindowsTaskScheduler:
    def __init__(self, schedule_args, command, task_name='MyTask', task_description='Scheduled Task'):
        self.schedule_args = schedule_args
        self.command = command
        self.task_name = task_name
        self.task_description = task_description

    def schedule(self, *, dry_run=False, start_date=None):
        if dry_run:
            return self.create_task_xml(start_date=start_date)
        raise WindowsPreviewError('Native task installation is unavailable; use a preview.')

    def create_task_xml(self, *, start_date=None, intervals=None):
        if not isinstance(start_date, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', start_date):
            raise WindowsPreviewError('Windows preview requires a start date in YYYY-MM-DD format.')
        try:
            date.fromisoformat(start_date)
        except ValueError:
            raise WindowsPreviewError('Invalid Windows start date.') from None
        if (not xml_safe(self.task_name) or not self.task_name.strip()
                or len(self.task_name) > 200 or any(c in self.task_name for c in '\\/:*?"<>|')
                or not xml_safe(self.task_description)):
            raise WindowsPreviewError('Invalid task name or description.')
        if (not isinstance(self.command, (list, tuple)) or not self.command
                or any(not xml_safe(arg) or '%' in arg for arg in self.command)
                or not PureWindowsPath(self.command[0]).is_absolute()
                or PureWindowsPath(self.command[0]).suffix.lower() != '.exe'
                or '"' in self.command[0]):
            raise WindowsPreviewError('Windows preview requires an absolute .exe and XML-safe arguments without percent characters.')
        times = [self.schedule_args] if intervals is None else intervals
        if not isinstance(times, (list, tuple)) or not 1 <= len(times) <= 48:
            raise WindowsPreviewError('Windows preview requires 1 to 48 daily triggers.')
        for time in times:
            if (not isinstance(time, (list, tuple)) or len(time) != 2
                    or any(type(v) is not int for v in time)
                    or not 0 <= time[0] < 24 or not 0 <= time[1] < 60):
                raise WindowsPreviewError('Invalid Windows daily trigger time.')
        root = ET.Element('Task', {'xmlns': NAMESPACE, 'version': '1.2'})
        registration = ET.SubElement(root, 'RegistrationInfo')
        ET.SubElement(registration, 'Description').text = self.task_description
        triggers = ET.SubElement(root, 'Triggers')
        for index, (hour, minute) in enumerate(times):
            trigger = ET.SubElement(triggers, 'CalendarTrigger', {'id': f'trigger{index}'})
            ET.SubElement(trigger, 'StartBoundary').text = f'{start_date}T{hour:02d}:{minute:02d}:00'
            ET.SubElement(trigger, 'Enabled').text = 'true'
            daily = ET.SubElement(trigger, 'ScheduleByDay')
            ET.SubElement(daily, 'DaysInterval').text = '1'
        actions = ET.SubElement(root, 'Actions')
        action = ET.SubElement(actions, 'Exec')
        ET.SubElement(action, 'Command').text = self.command[0]
        if len(self.command) > 1:
            ET.SubElement(action, 'Arguments').text = subprocess.list2cmdline(self.command[1:])
        ET.indent(root)
        return ET.tostring(root, encoding='utf-8', xml_declaration=True).decode('utf-8') + '\n'
