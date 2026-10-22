# Process Exit Observer

Windows PowerShell 5.1+ / PowerShell 7 on Windows. Observes one user-started game
or tool and records its native exit code. It never launches or terminates the
observed application, changes game settings, or installs anything. MIT.

```powershell
.\Watch-ProcessExit.ps1 -ExecutablePath "X:\Games\MyGame\game.exe" -OutputDirectory "X:\Reports\GameExit"
```

Start this observer, then start the application normally. It waits up to ten
minutes for the exact executable path, then observes up to thirty minutes. Use
`-WaitForStartSeconds` and `-MaxRunSeconds` to change those bounds. If several
instances share the path, supply `-TargetProcessId 1234`. The observer refuses
ambiguous matches. A timeout leaves the application alone.

Results are uniquely named JSON snapshots, including waiting, observation and
final state. There is no shared latest file to overwrite. The retained process
handle makes an exit code available after process exit. An exit code and a last
log line are evidence; neither alone proves a crash's root cause.

Snapshots include the selected executable's absolute path, process ID and times.
Review/redact them before sharing. Read access may be limited for elevated or
protected processes. Output directories containing links/junctions are refused.

Adapted from the locally authored bounded GAMMA test observer; all game paths
and installation assumptions were removed. No GAMMA/engine source is included.

Synthetic test (Python 3 and PowerShell on Windows):

```powershell
.\tests\Test-Observer.ps1 -PythonPath (Get-Command python.exe).Source
```

This starts short-lived Python fixture processes only, checks exit and timeout
results, and writes temporary reports. It does not start a game.
