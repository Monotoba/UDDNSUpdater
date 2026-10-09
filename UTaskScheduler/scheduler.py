"""Validate legacy Task sections using the unified daily planning API."""
import argparse
import configparser
import json
import re
import sys

if __package__:
    from .utask_scheduler import UTaskScheduler, SchedulerError, SchedulerUnavailableError
else:
    from utask_scheduler import UTaskScheduler, SchedulerError, SchedulerUnavailableError


def parse_config(config_file):
    config = configparser.ConfigParser(interpolation=None)
    try:
        with open(config_file, encoding='utf-8') as handle:
            config.read_file(handle)
    except (OSError, UnicodeError, configparser.Error):
        raise SchedulerError('Cannot read a valid UTF-8 task configuration.') from None
    if (config.defaults() or not config.sections()
            or any(not re.fullmatch(r'Task[1-9][0-9]*', section) for section in config.sections())):
        raise SchedulerError('Task configuration requires TaskN sections and no DEFAULT fields.')
    tasks = []
    names = set()
    fields = {'name', 'action', 'minutes', 'hours', 'days', 'weeks', 'months', 'years', 'date'}
    for section in config.sections():
        task = config[section]
        if set(task) - fields:
            raise SchedulerError('Unsupported task configuration field.')
        name = task.get('name', section).strip()
        if (not name or len(name) > 200 or any(ord(c) < 32 for c in name)
                or name.casefold() in names):
            raise SchedulerError('Task names must be nonempty, unique, and free of control characters.')
        names.add(name.casefold())
        try:
            action = json.loads(task.get('action', ''))
        except (ValueError, RecursionError):
            raise SchedulerError('Task action must be a JSON argument list.') from None
        action = UTaskScheduler.validate_command(action)
        if task.get('date', '').strip() or any(task.get(field, '*').strip() != '*'
                                               for field in ('days', 'weeks', 'months', 'years')):
            raise SchedulerError('Only daily tasks are supported; dates and calendar restrictions are unavailable.')
        minutes = task.get('minutes', '*/10')
        hours = task.get('hours', '*')
        UTaskScheduler.parse_cron_field(minutes, 60)
        UTaskScheduler.parse_cron_field(hours, 24)
        tasks.append({'name': name, 'action': action, 'minutes': minutes, 'hours': hours,
                      'days': '*', 'weeks': '*', 'months': '*', 'years': '*', 'date': ''})
    return tasks


def plan_tasks(config_file):
    """Validate all tasks before returning their daily triggers; never install."""
    tasks = parse_config(config_file)
    scheduler = UTaskScheduler()
    return [{'name': task['name'], 'triggers': [scheduler.schedule_task(task['action'], hour, minute, dry_run=True)
             for hour in scheduler.parse_cron_field(task['hours'], 24)
             for minute in scheduler.parse_cron_field(task['minutes'], 60)]} for task in tasks]


def main(argv=None):
    parser = argparse.ArgumentParser(description='Validate daily tasks in legacy TaskN sections')
    parser.add_argument('--config-file', default='config.ini')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    try:
        plans = plan_tasks(args.config_file)
        if not args.dry_run:
            raise SchedulerUnavailableError('Native task installation is unavailable; use --dry-run.')
    except SchedulerUnavailableError as error:
        print(str(error), file=sys.stderr)
        return 1
    except SchedulerError as error:
        print(str(error), file=sys.stderr)
        return 2
    count = sum(len(plan['triggers']) for plan in plans)
    print(f'Validated {len(plans)} task(s), {count} daily trigger(s). No tasks installed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
