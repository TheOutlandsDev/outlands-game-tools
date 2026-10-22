[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$PythonPath)
$ErrorActionPreference='Stop'
$taskPython=(Resolve-Path -LiteralPath $PythonPath).ProviderPath
$taskObserver=Join-Path (Split-Path -Parent $PSScriptRoot) 'Watch-ProcessExit.ps1'
$taskFixture=Join-Path ([IO.Path]::GetTempPath()) ('outlands-observer-test-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $taskFixture | Out-Null
$taskScript=Join-Path $taskFixture 'exit_fixture.py'
[IO.File]::WriteAllText($taskScript,"import time`ntime.sleep(3)`nraise SystemExit(7)`n")
$taskProcess=Start-Process -FilePath $taskPython -ArgumentList ('"'+$taskScript+'"') -WindowStyle Hidden -PassThru
$taskResult=& $taskObserver -ExecutablePath $taskPython -OutputDirectory (Join-Path $taskFixture 'exit') -TargetProcessId $taskProcess.Id -WaitForStartSeconds 5 -MaxRunSeconds 10 | ConvertFrom-Json
if($taskResult.status -ne 'PROCESS_EXIT_OBSERVED' -or $taskResult.exit_code_decimal -ne 7 -or $taskResult.exit_code_hex -ne '0x00000007') { throw 'Fixture exit code was not captured.' }
if($taskResult.process_started_by_observer -or $taskResult.process_stopped_by_observer) { throw 'Observer changed process ownership.' }
$taskMissing=& $taskObserver -ExecutablePath $taskPython -OutputDirectory (Join-Path $taskFixture 'missing') -TargetProcessId $taskProcess.Id -WaitForStartSeconds 1 -MaxRunSeconds 1 | ConvertFrom-Json
if($taskMissing.status -ne 'TIMED_OUT_WAITING_FOR_PROCESS') { throw 'Missing process did not time out.' }
[IO.File]::WriteAllText($taskScript,"import time`ntime.sleep(5)`n")
$taskLong=Start-Process -FilePath $taskPython -ArgumentList ('"'+$taskScript+'"') -WindowStyle Hidden -PassThru
$taskTimeout=& $taskObserver -ExecutablePath $taskPython -OutputDirectory (Join-Path $taskFixture 'timeout') -TargetProcessId $taskLong.Id -WaitForStartSeconds 3 -MaxRunSeconds 1 | ConvertFrom-Json
if($taskTimeout.status -ne 'OBSERVATION_TIMED_OUT_PROCESS_LEFT_RUNNING' -or $taskLong.HasExited) { throw 'Observer did not leave timed-out fixture running.' }
$taskLong.WaitForExit()
$taskSnapshots=@(Get-ChildItem -LiteralPath (Join-Path $taskFixture 'exit') -File)
if($taskSnapshots.Count -ne 3) { throw 'Expected three independent exit snapshots.' }
$taskStateSequence=@($taskSnapshots | Sort-Object Name | ForEach-Object { (Get-Content -LiteralPath $_.FullName -Raw | ConvertFrom-Json).status })
if(($taskStateSequence -join ',') -ne 'WAITING_FOR_PROCESS,OBSERVING_PROCESS,PROCESS_EXIT_OBSERVED') { throw 'Snapshot sequence mismatch.' }
[ordered]@{status='PASS';checks=5;fixture_directory=$taskFixture;games_launched=0} | ConvertTo-Json
