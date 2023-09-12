# UTaskScheduler Module User Manual

The UTaskScheduler module is designed as a generic task scheduler to simplify the process of scheduling tasks on different operating systems. This user manual will guide you through the usage of the module, explain its implementation, and provide code examples for incorporating it into your projects.

## Table of Contents
1. [Installation](#installation)
2. [Module Overview](#module-overview)
3. [Usage Examples](#usage-examples)
    - [Scheduling Tasks](#scheduling-tasks)
4. [Scheduler Script (`scheduler.py`)](#scheduler-script)
    - [Config File Format](#config-file-format)
    - [Examples](#examples)
5. [Implementation Details](#implementation-details)
    - [Windows Task Scheduler](#windows-task-scheduler)
    - [Unix Task Scheduler](#unix-task-scheduler)
    - [Mac Task Scheduler](#mac-task-scheduler)
6. [Conclusion](#conclusion)

## 1. Installation <a name="installation"></a>

The UTaskScheduler module is part of your Python project and does not require separate installation.

## 2. Module Overview <a name="module-overview"></a>

The UTaskScheduler module is designed as a generic task scheduler to simplify the process of scheduling various tasks on different operating systems. It provides a unified interface and platform-specific implementations.

## 3. Usage Examples <a name="usage-examples"></a>

### Scheduling Tasks <a name="scheduling-tasks"></a>

To schedule tasks on different operating systems, you can use the `UTaskScheduler` class. Define the command you want to schedule as a list of strings and pass it to the `schedule` method.

## 4. Scheduler Script (`scheduler.py`) <a name="scheduler-script"></a>

The `scheduler.py` script allows you to schedule tasks using the UTaskScheduler module. It reads a `config.ini` file to define and schedule tasks.

### Config File Format

The config.ini file should follow this format:

```ini
[Task1]
name = Task 1
action = ["python", "myscript.py", "--arg1", "--arg2", ...]
minutes = */10
hours = *
days = *
weeks = *
months = *
years = *

; Additional tasks...
```

- **name**: A name for the task.
- **action**: The command to execute, provided as a list of strings.
- **minutes, hours, days, weeks, months, years**: Cron-like scheduling parameters. Use * for any, or provide specific values. 
Note that cron-like intervals */5, are supported. The */X form means at Intervals of X.

### Examples

Example 1: Schedule a Python Script (Recurring)

To schedule recurring execution of a Python script, configure your config.ini file as follows:

```ini
[Task1]
name = Task 1
action = ["python", "myscript.py", "--arg1", "--arg2"]
minutes = */10
hours = *
days = *
weeks = *
months = *
years = *
```

Example 2: Schedule a Shell Script (Recurring)

To schedule the execution of a shell script, you should define a task in config.ini like this:

```ini
[Task1]
name = Task 1
action = ["bash", "myscript.sh"]
minutes = */10
hours = *
days = *
weeks = *
months = *
years = *
```

Example 3: Schedule a Batch File (Recurring)

To schedule the execution of a batch file, your config.ini should contain a task like this:

```ini
[Task1]
name = Task 1
action = ["cmd", "/c", "myscript.bat"]
minutes = */10
hours = *
days = *
weeks = *
months = *
years = *
```

## 5. Implementation Details <a name="implementation-details"></a>

### Windows Task Scheduler <a name="windows-task-scheduler"></a>

The `WindowsTaskScheduler` class uses the Windows Task Scheduler to create scheduled tasks.

### Unix Task Scheduler <a name="unix-task-scheduler"></a>

The `UnixTaskScheduler` class schedules tasks on Linux and most Unix-Like operating system using the `cron` job scheduler.

### Mac Task Scheduler <a name="mac-task-scheduler"></a>

The `MacTaskScheduler` class schedules tasks on macOS using launchd.

## 6. Conclusion <a name="conclusion"></a>

The UTaskScheduler module simplifies the process of scheduling various tasks on Windows, macOS, and Linux. The `scheduler.py` script provides a convenient way to define and schedule tasks using a `config.ini` file. Incorporate this module into your projects to automate various tasks and improve your system's reliability.
