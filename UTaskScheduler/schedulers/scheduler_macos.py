"""macOS launchd definition generation; installation remains disabled."""
import plistlib
import re


class LaunchdPreviewError(ValueError):
    """Controlled definition or installation error."""


class MacTaskScheduler:
    def __init__(self, schedule_args, system_task=False, *, command=None,
                 label="org.monotoba.uddnsupdater"):
        self.schedule_args = schedule_args
        self.system_task = system_task
        self.command = command
        self.label = label

    def render_plist(self, *, intervals=None):
        if self.system_task:
            raise LaunchdPreviewError("System launchd definitions are unavailable.")
        if (not isinstance(self.label, str) or len(self.label) > 200
                or not re.fullmatch(r"[A-Za-z0-9]+(?:[.-][A-Za-z0-9_-]+)+", self.label)):
            raise LaunchdPreviewError("Invalid launchd label.")
        if (not isinstance(self.command, (list, tuple)) or not self.command
                or not isinstance(self.command[0], str) or not self.command[0].startswith("/")
                or any(not isinstance(arg, str) or any(ord(c) < 32 and c != "\t" for c in arg)
                       or any(0xD800 <= ord(c) <= 0xDFFF or ord(c) in (0xFFFE, 0xFFFF) for c in arg)
                       for arg in self.command)):
            raise LaunchdPreviewError("Launchd preview requires XML-safe arguments and an absolute executable.")
        times = [self.schedule_args] if intervals is None else intervals
        if not isinstance(times, (list, tuple)) or not times:
            raise LaunchdPreviewError("Launchd preview requires daily trigger times.")
        calendar = []
        for time in times:
            if (not isinstance(time, (list, tuple)) or len(time) != 2
                    or any(type(value) is not int for value in time)
                    or not 0 <= time[0] < 24 or not 0 <= time[1] < 60):
                raise LaunchdPreviewError("Invalid launchd daily trigger time.")
            calendar.append({"Hour": time[0], "Minute": time[1]})
        return plistlib.dumps({"Label": self.label, "ProgramArguments": list(self.command),
                              "StartCalendarInterval": calendar}, sort_keys=False).decode("utf-8")

    def schedule(self, *, dry_run=False):
        if dry_run:
            return self.render_plist()
        raise LaunchdPreviewError("Native task installation is unavailable; use a preview.")

    def create_system_task(self, *args, **kwargs):
        raise LaunchdPreviewError("Native task installation is unavailable; use a preview.")

    def create_user_task(self, *args, **kwargs):
        raise LaunchdPreviewError("Native task installation is unavailable; use a preview.")

    def write_plist_file(self, *args, **kwargs):
        raise LaunchdPreviewError("Native task installation is unavailable; use a preview.")
