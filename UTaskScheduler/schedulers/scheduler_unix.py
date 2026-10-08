"""Linux user-crontab generation; native installation remains disabled."""
import shlex


class CronPreviewError(ValueError):
    """Controlled cron definition or installation error."""


class UnixTaskScheduler:
    def __init__(self, schedule_args, command, system_task=False):
        self.schedule_args = schedule_args
        self.command = command
        self.system_task = system_task

    def render_cron_line(self):
        if self.system_task:
            raise CronPreviewError('System crontab generation is unavailable.')
        if (not isinstance(self.schedule_args, (list, tuple)) or len(self.schedule_args) != 2
                or any(type(value) is not int for value in self.schedule_args)
                or not 0 <= self.schedule_args[0] < 24
                or not 0 <= self.schedule_args[1] < 60):
            raise CronPreviewError('Cron preview requires an hour and minute.')
        if (not isinstance(self.command, (list, tuple)) or not self.command
                or not isinstance(self.command[0], str) or not self.command[0].startswith('/')
                or any(not isinstance(arg, str) or any(c in arg for c in "\x00\r\n")
                       for arg in self.command)):
            raise CronPreviewError('Cron preview requires an absolute executable and argument list.')
        # Separate each percent into its own quoted fragment. This avoids a
        # preceding literal backslash consuming cron's percent escape.
        command = ' '.join("'\\%'".join(shlex.quote(part) for part in arg.split('%'))
                           for arg in self.command)
        hour, minute = self.schedule_args
        return f'{minute} {hour} * * * {command}'

    def render_cron(self):
        return 'SHELL=/bin/sh\n' + self.render_cron_line() + '\n'

    def schedule(self, *, dry_run=False):
        return self.schedule_linux(dry_run=dry_run)

    def schedule_linux(self, *, dry_run=False):
        preview = self.render_cron()
        if dry_run:
            return preview
        raise CronPreviewError('Native task installation is unavailable; use a preview.')

    def schedule_macos(self):
        raise CronPreviewError('Use the macOS backend; native installation is unavailable.')
