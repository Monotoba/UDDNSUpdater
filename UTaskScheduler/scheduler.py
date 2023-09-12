import configparser
from utask_scheduler import UTaskScheduler

def parse_config(config_file):
    config = configparser.ConfigParser()
    config.read(config_file)

    tasks = []

    for section_name in config.sections():
        if section_name.startswith("Task"):
            task = config[section_name]
            task_name = task.get("name", f"Unnamed Task ({section_name})")
            task_action = task.get("action", "").split()
            task_minutes = task.get("minutes", "*/10")
            task_hours = task.get("hours", "*")
            task_days = task.get("days", "*")
            task_weeks = task.get("weeks", "*")
            task_months = task.get("months", "*")
            task_years = task.get("years", "*")

            tasks.append({
                "name": task_name,
                "action": task_action,
                "minutes": task_minutes,
                "hours": task_hours,
                "days": task_days,
                "weeks": task_weeks,
                "months": task_months,
                "years": task_years,
            })

    return tasks

def main():
    config_file = "config.ini"  # Update with your config file path
    tasks = parse_config(config_file)

    scheduler = UTaskScheduler()

    for task in tasks:
        name = task["name"]
        action = task["action"]
        minutes = task["minutes"]
        hours = task["hours"]
        days = task["days"]
        weeks = task["weeks"]
        months = task["months"]
        years = task["years"]

        # Schedule the task with UTaskScheduler
        scheduler.schedule(action, minutes, hours, days, weeks, months, years)
        print(f"Scheduled task '{name}'.")

if __name__ == "__main__":
    main()
