# UTaskScheduler Module User Manual

The UTaskScheduler module is designed as a generic task scheduler to simplify the process of scheduling tasks on different operating systems. This user manual will guide you through the usage of the module, explain its implementation, and provide code examples for incorporating it into your projects.

## Table of Contents
1. [Installation](#installation)
2. [Module Overview](#module-overview)
3. [Usage Examples](#usage-examples)
    - [Scheduling Tasks](#scheduling-tasks)
4. [Implementation Details](#implementation-details)
    - [Windows Task Scheduler](#windows-task-scheduler)
    - [Unix Task Scheduler](#unix-task-scheduler)
    - [Mac Task Scheduler](#mac-task-scheduler)
5. [Conclusion](#conclusion)

## 1. Installation <a name="installation"></a>

The UTaskScheduler module is part of your Python project and does not require separate installation.

## 2. Module Overview <a name="module-overview"></a>

The UTaskScheduler module is designed as a generic task scheduler to simplify the process of scheduling various tasks on different operating systems. It achieves this by providing a unified interface (`UTaskScheduler`) and platform-specific implementations (`WindowsTaskScheduler`, `UnixTaskScheduler`, and `MacTaskScheduler`). The module uses Python's built-in libraries and subprocess calls to interact with the underlying scheduling mechanisms of each operating system.

## 3. Usage Examples <a name="usage-examples"></a>

### Scheduling Tasks <a name="scheduling-tasks"></a>

To schedule tasks on different operating systems, you can use the `UTaskScheduler` class. Define the command you want to schedule as a list of strings and pass it to the `schedule` method. Here's an example:

```python
from scheduler.utscheduler import UTaskScheduler

# Create an instance of UTaskScheduler
scheduler = UTaskScheduler()

# Define the command you want to schedule (e.g., running a script)
task_command = ["python", "my_script.py", "--arg1", "--arg2"]

# Schedule the command
scheduler.schedule(task_command)
```

## 4. Implementation Details <a name="implementation-details"></a>

### Windows Task Scheduler <a name="windows-task-scheduler"></a>

The `WindowsTaskScheduler` class uses the Windows Task Scheduler to create scheduled tasks. It generates an XML task definition, writes it to a temporary file, and uses the `schtasks` command to create the task. Here are the key methods:

- `schedule`: Creates a scheduled task.
- `create_task_xml`: Generates the XML task definition.
- `write_plist_file`: Writes the XML definition to a temporary file.
- `create_system_task`: Creates a system-level task.
- `create_user_task`: Creates a user-level task.

### Unix Task Scheduler <a name="unix-task-scheduler"></a>

The `UnixTaskScheduler` class schedules tasks on both Linux and macOS. It uses the `cron` job scheduler to add tasks to the system's crontab. Here are the key methods:

- `schedule`: Schedules tasks based on the operating system.
- `schedule_linux`: Schedules tasks on Linux using the `crontab` command.
- `schedule_macos`: Displays a message as macOS does not support `cron` directly.

### Mac Task Scheduler <a name="mac-task-scheduler"></a>

The `MacTaskScheduler` class schedules tasks on macOS using launchd. It creates a `.plist` file describing the task and loads it into launchd. Here are the key methods:

- `schedule`: Schedules tasks based on whether they are system-level or user-level.
- `create_system_task`: Creates a system-level task using launchd.
- `create_user_task`: Creates a user-level task using launchd.
- `write_plist_file`: Writes the `.plist` file.

## 5. Conclusion <a name="conclusion"></a>

The UTaskScheduler module simplifies the process of scheduling various tasks on Windows, macOS, and Linux. By providing a unified interface and platform-specific implementations, it allows you to manage your scheduled tasks seamlessly across different operating systems. Incorporate this module into your projects to automate various tasks and improve your system's reliability.
```

This updated manual describes the generic `UTaskScheduler` module for scheduling tasks on different operating systems without referencing any specific task, making it more versatile for various scheduling needs.
