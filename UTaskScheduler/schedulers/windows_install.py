"""Explicit current-user interactive Windows Task Scheduler registration."""
import json
import os
from pathlib import PureWindowsPath
import re
import subprocess
import xml.etree.ElementTree as ET

from .scheduler_windows import NAMESPACE, WindowsPreviewError, WindowsTaskScheduler

MARKER = 'UDDNSUpdater managed daily task v1'
IDENTITY_SCRIPT = r'''
function Test-CurrentUser([string]$identity, [string]$sid) {
    try {
        if ($identity -match '^S-[0-9-]+$') {
            $resolved = [System.Security.Principal.SecurityIdentifier]::new($identity).Value
        } else {
            $account = [System.Security.Principal.NTAccount]::new($identity)
            $resolved = $account.Translate([System.Security.Principal.SecurityIdentifier]).Value
        }
        return $resolved -eq $sid
    } catch { return $false }
}
'''
SCRIPT = r'''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
''' + IDENTITY_SCRIPT + r'''
$phase = 'input'
try {
    $p = [Console]::In.ReadToEnd() | ConvertFrom-Json
    $sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $tasks = @(Get-ScheduledTask -TaskPath '\' -ErrorAction Stop)
    $task = @($tasks | Where-Object { $_.TaskName -eq $p.name })
    if ($p.operation -eq 'install') {
        $phase = 'collision'
        if ($task.Count -ne 0) { throw 'collision' }
        [xml]$definition = $p.xml
        $ns = New-Object System.Xml.XmlNamespaceManager($definition.NameTable)
        $ns.AddNamespace('t', 'http://schemas.microsoft.com/windows/2004/02/mit/task')
        $definition.SelectSingleNode('//t:UserId', $ns).InnerText = $sid
        $phase = 'registration'
        Register-ScheduledTask -TaskName $p.name -TaskPath '\' -Xml $definition.OuterXml -ErrorAction Stop | Out-Null
        $created = Get-ScheduledTask -TaskName $p.name -TaskPath '\' -ErrorAction Stop
        $phase = 'identity'
        if ($created.Description -ne $p.marker -or -not (Test-CurrentUser $created.Principal.UserId $sid)) { throw 'verification' }
        $phase = 'export'
        $export = Export-ScheduledTask -TaskName $p.name -TaskPath '\' -ErrorAction Stop
        @{ok=$true; xml=$export} | ConvertTo-Json -Compress
    } elseif ($p.operation -eq 'remove') {
        $phase = 'ownership'
        if ($task.Count -ne 1 -or $task[0].Description -ne $p.marker -or -not (Test-CurrentUser $task[0].Principal.UserId $sid)) { throw 'ownership' }
        $phase = 'removal'
        Unregister-ScheduledTask -TaskName $p.name -TaskPath '\' -Confirm:$false -ErrorAction Stop
        $remaining = @(Get-ScheduledTask -TaskPath '\' -ErrorAction Stop | Where-Object { $_.TaskName -eq $p.name })
        if ($remaining.Count -ne 0) { throw 'verification' }
        @{ok=$true} | ConvertTo-Json -Compress
    } else { throw 'operation' }
} catch {
    [Console]::Error.WriteLine('UDDNS native failure phase: ' + $phase)
    exit 1
}
'''


def task_name(name):
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', name):
        raise WindowsPreviewError('Task name must use 1–64 letters, digits, underscores or hyphens.')
    return 'UDDNSUpdater-'+name


def invoke(operation, name, definition=None):
    name = task_name(name)
    root = os.environ.get('SystemRoot', '')
    if not root or not PureWindowsPath(root).is_absolute():
        raise WindowsPreviewError('Cannot locate Windows PowerShell.')
    executable = str(PureWindowsPath(root)/'System32'/'WindowsPowerShell'/'v1.0'/'powershell.exe')
    try:
        result = subprocess.run([executable, '-NoProfile', '-NonInteractive', '-Command', SCRIPT],
                                input=json.dumps({'operation':operation, 'name':name,
                                                  'xml':definition, 'marker':MARKER}),
                                capture_output=True, text=True, encoding='utf-8', timeout=30)
        if result.returncode:
            phase = re.fullmatch(r'UDDNS native failure phase: (input|collision|registration|identity|export|ownership|removal)',
                                 result.stderr.strip())
            if phase:
                raise WindowsPreviewError('Native task operation failed during ' + phase.group(1)
                                          + '; inspect Task Scheduler before retrying.')
            raise ValueError
        if len(result.stdout) > 524288:
            raise ValueError
        response = json.loads(result.stdout.lstrip('\ufeff'))
        if not isinstance(response, dict) or response.get('ok') is not True:
            raise ValueError
        return response
    except (OSError, subprocess.SubprocessError, UnicodeError, ValueError):
        raise WindowsPreviewError('Native task operation failed; inspect Task Scheduler before retrying.') from None


def install(name, command, intervals, start_date):
    full_name = task_name(name)
    if not isinstance(intervals, (list, tuple)) or not intervals:
        raise WindowsPreviewError('Daily trigger times are required.')
    text = WindowsTaskScheduler(intervals[0], command, task_name=full_name,
                                task_description=MARKER).create_task_xml(start_date=start_date, intervals=intervals)
    root = ET.fromstring(text)
    q = lambda name: '{'+NAMESPACE+'}'+name
    principals = ET.Element(q('Principals'))
    principal = ET.SubElement(principals, q('Principal'), {'id':'CurrentUser'})
    ET.SubElement(principal, q('UserId')).text = 'CURRENT_USER_SID'
    ET.SubElement(principal, q('LogonType')).text = 'InteractiveToken'
    ET.SubElement(principal, q('RunLevel')).text = 'LeastPrivilege'
    root.insert(2, principals)
    root.find(q('Actions')).set('Context', 'CurrentUser')
    definition = ET.tostring(root, encoding='unicode')
    response = invoke('install', name, definition)
    try:
        exported = response['xml']
        if not isinstance(exported, str) or '<!DOCTYPE' in exported.upper():
            raise ValueError
        actual = ET.fromstring(exported)
        for tag in ('Command', 'Arguments', 'Description', 'LogonType', 'RunLevel'):
            expected = root.find('.//'+q(tag))
            received = actual.find('.//'+q(tag))
            if (None if expected is None else expected.text) != (None if received is None else received.text):
                raise ValueError
        expected_times = [x.text for x in root.findall('.//'+q('StartBoundary'))]
        actual_times = [x.text for x in actual.findall('.//'+q('StartBoundary'))]
        if expected_times != actual_times:
            raise ValueError
    except (KeyError, TypeError, ValueError, ET.ParseError):
        raise WindowsPreviewError('Task registered but definition verification failed; inspect Task Scheduler.') from None


def remove(name):
    invoke('remove', name)
