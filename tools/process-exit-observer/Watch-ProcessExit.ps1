# SPDX-License-Identifier: MIT
# Observes one explicitly selected process. Never starts or terminates it.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ExecutablePath,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [ValidateRange(0,2147483647)][int]$TargetProcessId=0,
    [ValidateRange(1,3600)][int]$WaitForStartSeconds=600,
    [ValidateRange(1,86400)][int]$MaxRunSeconds=1800
)
$ErrorActionPreference='Stop'
$taskExecutable=(Resolve-Path -LiteralPath $ExecutablePath).ProviderPath
if(-not [IO.File]::Exists($taskExecutable)) { throw 'ExecutablePath must be a file.' }
$taskOutput=[IO.Path]::GetFullPath($OutputDirectory)
$taskProbe=$taskOutput
while($taskProbe) {
    if(Test-Path -LiteralPath $taskProbe) {
        $taskItem=Get-Item -LiteralPath $taskProbe -Force
        if(($taskItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'OutputDirectory cannot contain links or junctions.' }
    }
    $taskParent=[IO.Path]::GetDirectoryName($taskProbe)
    if($taskParent -eq $taskProbe) { break }
    $taskProbe=$taskParent
}
[IO.Directory]::CreateDirectory($taskOutput) | Out-Null
$script:taskRunId=[datetime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')+'-'+[guid]::NewGuid().ToString('N')
$script:taskSequence=0
$taskState=[ordered]@{
    status='WAITING_FOR_PROCESS'; observer_started_utc=[datetime]::UtcNow.ToString('o')
    expected_executable=$taskExecutable; requested_process_id=$TargetProcessId
    process_started_by_observer=$false; process_stopped_by_observer=$false
}
function Write-ObserverState {
    $script:taskSequence++
    $taskSnapshot=Join-Path $taskOutput ('process-exit.'+$script:taskRunId+'.'+$script:taskSequence.ToString('D3')+'.json')
    $taskState.snapshot_sequence=$script:taskSequence
    $taskJson=$taskState | ConvertTo-Json -Depth 4
    # Each result is independent and never replaces an earlier observer's result.
    $taskBytes=[Text.UTF8Encoding]::new($false).GetBytes($taskJson)
    $taskStream=[IO.File]::Open($taskSnapshot,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
    try { $taskStream.Write($taskBytes,0,$taskBytes.Length); $taskStream.Flush() }
    finally { $taskStream.Dispose() }
}
$taskObserved=$null
Write-ObserverState
try {
    $taskDeadline=[datetime]::UtcNow.AddSeconds($WaitForStartSeconds)
    while([datetime]::UtcNow -lt $taskDeadline) {
        $taskCandidates=@(Get-Process -ErrorAction SilentlyContinue | Where-Object {
            ($TargetProcessId -eq 0 -or $_.Id -eq $TargetProcessId) -and $_.Path -ieq $taskExecutable
        })
        if($taskCandidates.Count -gt 1) { throw 'Multiple matching processes. Supply TargetProcessId to select one.' }
        if($taskCandidates.Count -eq 1) { $taskObserved=$taskCandidates[0]; break }
        Start-Sleep -Milliseconds 200
    }
    if($null -eq $taskObserved) {
        $taskState.status='TIMED_OUT_WAITING_FOR_PROCESS'
        Write-ObserverState
        $taskState | ConvertTo-Json -Depth 4
        return
    }
    # Retain a handle while the process exists so its actual exit code survives.
    $null=$taskObserved.Handle
    if($taskObserved.Path -ine $taskExecutable) { throw 'Process executable changed during selection.' }
    $taskState.status='OBSERVING_PROCESS'
    $taskState.process_id=$taskObserved.Id
    $taskState.process_started_utc=$taskObserved.StartTime.ToUniversalTime().ToString('o')
    Write-ObserverState
    if($taskObserved.WaitForExit($MaxRunSeconds*1000)) {
        $taskExit=$taskObserved.ExitCode
        $taskState.status='PROCESS_EXIT_OBSERVED'
        $taskState.exit_code_decimal=$taskExit
        $taskState.exit_code_hex='0x'+(([long]$taskExit -band 4294967295).ToString('X8'))
        $taskState.observed_exit_utc=[datetime]::UtcNow.ToString('o')
    } else {
        $taskState.status='OBSERVATION_TIMED_OUT_PROCESS_LEFT_RUNNING'
    }
    Write-ObserverState
    $taskState | ConvertTo-Json -Depth 4
} catch {
    $taskState.status='OBSERVER_ERROR'
    $taskState.error=$_.Exception.Message
    Write-ObserverState
    throw
} finally {
    if($null -ne $taskObserved) { $taskObserved.Dispose() }
}
