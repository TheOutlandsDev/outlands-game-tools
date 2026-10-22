param(
    [string] $Path,
    [string] $DiagnosticsDirectory,
    [switch] $ComparePrevious
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($DiagnosticsDirectory)) {
    if ([string]::IsNullOrWhiteSpace($Path)) {
        throw 'Provide -Path to a JSONL file or -DiagnosticsDirectory to a capture directory.'
    }
    $DiagnosticsDirectory = Split-Path -Parent (Get-Item -LiteralPath $Path).FullName
}
$diagnosticsDir = $DiagnosticsDirectory

if ([string]::IsNullOrWhiteSpace($Path)) {
    $latest = Get-ChildItem -LiteralPath $diagnosticsDir -File -Filter "client-*.jsonl" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if ($null -eq $latest) {
        throw "No diagnostics files found in $diagnosticsDir"
    }

    $Path = $latest.FullName
}

function Read-DiagnosticsEvents {
    param([string] $FilePath)

    foreach ($line in Get-Content -LiteralPath $FilePath) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        try {
            $line | ConvertFrom-Json
        } catch {
            [pscustomobject]@{
                type = "parse_error"
                utc = $null
                payload = [pscustomobject]@{
                    message = $_.Exception.Message
                    line = $line
                }
            }
        }
    }
}

function Get-PluginGuids {
    param($Events)

    $snapshot = @($Events | Where-Object { $_.type -eq "bepinex_plugins" } | Select-Object -Last 1)
    if ($snapshot.Count -eq 0 -or $null -eq $snapshot[0].payload.plugins) {
        return @()
    }

    @($snapshot[0].payload.plugins | ForEach-Object { $_.guid } | Where-Object { $_ })
}

function Get-ServerModNames {
    param($Events)

    $snapshot = @($Events | Where-Object { $_.type -eq "server_mod_folders" } | Select-Object -Last 1)
    if ($snapshot.Count -eq 0 -or $null -eq $snapshot[0].payload.entries) {
        return @()
    }

    @($snapshot[0].payload.entries | ForEach-Object { $_.name } | Where-Object { $_ })
}

function Get-NumberOrNull {
    param($Value)

    if ($null -eq $Value -or $Value -eq "") {
        return $null
    }

    try {
        return [double]$Value
    } catch {
        return $null
    }
}

function Get-NumberArray {
    param(
        [object[]] $Items,
        [scriptblock] $Expression
    )

    $values = New-Object System.Collections.Generic.List[double]
    foreach ($item in $Items) {
        try {
            $number = Get-NumberOrNull (& $Expression $item)
            if ($null -ne $number) {
                [void]$values.Add($number)
            }
        } catch {
        }
    }

    $values.ToArray()
}

function Get-NumberSum {
    param(
        [object[]] $Items,
        [scriptblock] $Expression
    )

    $sum = 0.0
    foreach ($item in $Items) {
        try {
            $number = Get-NumberOrNull (& $Expression $item)
            if ($null -ne $number) {
                $sum += $number
            }
        } catch {
        }
    }

    $sum
}

function Get-RoundedAverage {
    param([double[]] $Values)

    if ($null -eq $Values -or $Values.Count -eq 0) {
        return $null
    }

    [math]::Round(($Values | Measure-Object -Average).Average, 2)
}

function Get-RoundedMinimum {
    param([double[]] $Values)

    if ($null -eq $Values -or $Values.Count -eq 0) {
        return $null
    }

    [math]::Round(($Values | Measure-Object -Minimum).Minimum, 2)
}

function Get-RoundedMaximum {
    param([double[]] $Values)

    if ($null -eq $Values -or $Values.Count -eq 0) {
        return $null
    }

    [math]::Round(($Values | Measure-Object -Maximum).Maximum, 2)
}

$events = @(Read-DiagnosticsEvents -FilePath $Path)

Write-Host "Diagnostics summary"
Write-Host "File: $Path"
Write-Host ""

Write-Host "Event counts"
$events | Group-Object type | Sort-Object Count -Descending | Select-Object Count,Name | Format-Table -AutoSize

$session = @($events | Where-Object { $_.type -eq "session_start" } | Select-Object -First 1)
if ($session.Count -gt 0) {
    Write-Host "Session"
    $session[0].payload | Format-List
}

$samples = @($events | Where-Object { $_.type -eq "performance_sample" })
if ($samples.Count -gt 0) {
    $fpsValues = @(Get-NumberArray -Items $samples -Expression { param($event) $event.payload.fps })
    $maxFrameValues = @(Get-NumberArray -Items $samples -Expression { param($event) $event.payload.max_frame_ms })
    $p95FrameValues = @(Get-NumberArray -Items $samples -Expression { param($event) $event.payload.p95_frame_ms })
    $p99FrameValues = @(Get-NumberArray -Items $samples -Expression { param($event) $event.payload.p99_frame_ms })
    $hitches = [int](Get-NumberSum -Items $samples -Expression { param($event) $event.payload.hitch_count })
    $bucketLe16 = [int](Get-NumberSum -Items $samples -Expression { param($event) $event.payload.frame_buckets.le_16_7_ms })
    $bucketLe33 = [int](Get-NumberSum -Items $samples -Expression { param($event) $event.payload.frame_buckets.le_33_3_ms })
    $bucketLe50 = [int](Get-NumberSum -Items $samples -Expression { param($event) $event.payload.frame_buckets.le_50_ms })
    $bucketLe100 = [int](Get-NumberSum -Items $samples -Expression { param($event) $event.payload.frame_buckets.le_100_ms })
    $bucketGt100 = [int](Get-NumberSum -Items $samples -Expression { param($event) $event.payload.frame_buckets.gt_100_ms })
    $gc0 = [int](Get-NumberSum -Items $samples -Expression { param($event) $event.payload.gc.gen0_delta })
    $gc1 = [int](Get-NumberSum -Items $samples -Expression { param($event) $event.payload.gc.gen1_delta })
    $gc2 = [int](Get-NumberSum -Items $samples -Expression { param($event) $event.payload.gc.gen2_delta })

    Write-Host "Performance"
    [pscustomobject]@{
        Samples = $samples.Count
        AvgFps = Get-RoundedAverage -Values $fpsValues
        MinFps = Get-RoundedMinimum -Values $fpsValues
        WorstFrameMs = Get-RoundedMaximum -Values $maxFrameValues
        WorstP95FrameMs = Get-RoundedMaximum -Values $p95FrameValues
        WorstP99FrameMs = Get-RoundedMaximum -Values $p99FrameValues
        SampleHitches = $hitches
        FramesLe16_7Ms = $bucketLe16
        FramesLe33_3Ms = $bucketLe33
        FramesLe50Ms = $bucketLe50
        FramesLe100Ms = $bucketLe100
        FramesGt100Ms = $bucketGt100
        GcGen0Collections = $gc0
        GcGen1Collections = $gc1
        GcGen2Collections = $gc2
    } | Format-List
}

$systemSamples = @($events | Where-Object { $_.type -eq "system_sample" })
if ($systemSamples.Count -gt 0) {
    $cpuValues = @(Get-NumberArray -Items $systemSamples -Expression { param($event) $event.payload.process.cpu_percent })
    $workingSetValues = @(Get-NumberArray -Items $systemSamples -Expression { param($event) $event.payload.process.working_set_mb })
    $privateValues = @(Get-NumberArray -Items $systemSamples -Expression { param($event) $event.payload.process.private_mb })
    $threadValues = @(Get-NumberArray -Items $systemSamples -Expression { param($event) $event.payload.process.thread_count })
    $managedValues = @(Get-NumberArray -Items $systemSamples -Expression { param($event) $event.payload.memory.managed_mb })
    $allocatedValues = @(Get-NumberArray -Items $systemSamples -Expression { param($event) $event.payload.memory.allocated_mb })
    $reservedValues = @(Get-NumberArray -Items $systemSamples -Expression { param($event) $event.payload.memory.reserved_mb })

    Write-Host "System samples"
    [pscustomobject]@{
        Samples = $systemSamples.Count
        AvgCpuPercent = Get-RoundedAverage -Values $cpuValues
        MaxCpuPercent = Get-RoundedMaximum -Values $cpuValues
        MaxWorkingSetMb = Get-RoundedMaximum -Values $workingSetValues
        MaxPrivateMb = Get-RoundedMaximum -Values $privateValues
        MaxThreads = Get-RoundedMaximum -Values $threadValues
        MaxManagedMb = Get-RoundedMaximum -Values $managedValues
        MaxAllocatedMb = Get-RoundedMaximum -Values $allocatedValues
        MaxReservedMb = Get-RoundedMaximum -Values $reservedValues
    } | Format-List
}

$raidSamples = @($events | Where-Object { $_.type -eq "raid_sample" })
if ($raidSamples.Count -gt 0) {
    $inRaidSamples = @($raidSamples | Where-Object { $_.payload.in_raid -eq $true })
    $alivePlayerValues = @(Get-NumberArray -Items $inRaidSamples -Expression { param($event) $event.payload.alive_players })
    $botOwnerValues = @(Get-NumberArray -Items $inRaidSamples -Expression { param($event) $event.payload.bot_owners })
    $aliveBotOwnerValues = @(Get-NumberArray -Items $inRaidSamples -Expression { param($event) $event.payload.alive_bot_owners })
    $locations = @($inRaidSamples | ForEach-Object { $_.payload.location } | Where-Object { $_ } | Sort-Object -Unique)

    Write-Host "Raid samples"
    [pscustomobject]@{
        Samples = $raidSamples.Count
        InRaidSamples = $inRaidSamples.Count
        Locations = ($locations -join ", ")
        MaxAlivePlayers = Get-RoundedMaximum -Values $alivePlayerValues
        MaxBotOwners = Get-RoundedMaximum -Values $botOwnerValues
        MaxAliveBotOwners = Get-RoundedMaximum -Values $aliveBotOwnerValues
    } | Format-List
}

$hitchEvents = @($events | Where-Object { $_.type -eq "hitch" } | Sort-Object { [double]$_.payload.frame_ms } -Descending)
if ($hitchEvents.Count -gt 0) {
    Write-Host "Worst hitches"
    $hitchEvents |
        Select-Object -First 15 @{Name="utc";Expression={$_.utc}},
            @{Name="frame_ms";Expression={$_.payload.frame_ms}},
            @{Name="scene";Expression={$_.payload.scene}},
            @{Name="location";Expression={$_.payload.raid.location}},
            @{Name="alive_bots";Expression={$_.payload.raid.alive_bot_owners}},
            @{Name="cpu_pct";Expression={$_.payload.process.cpu_percent}},
            @{Name="managed_mb";Expression={$_.payload.memory.managed_mb}},
            @{Name="allocated_mb";Expression={$_.payload.memory.allocated_mb}},
            @{Name="gc0";Expression={$_.payload.memory.gc_gen0}},
            @{Name="gc1";Expression={$_.payload.memory.gc_gen1}},
            @{Name="gc2";Expression={$_.payload.memory.gc_gen2}} |
        Format-Table -AutoSize
}

$unityLogs = @($events | Where-Object { $_.type -eq "unity_log" })
if ($unityLogs.Count -gt 0) {
    Write-Host "Unity logs by level"
    $unityLogs | Group-Object { $_.payload.level } | Sort-Object Count -Descending | Select-Object Count,Name | Format-Table -AutoSize

    Write-Host "Top Unity messages"
    $unityLogs |
        Group-Object { "$($_.payload.level): $($_.payload.message)" } |
        Sort-Object Count -Descending |
        Select-Object -First 15 Count,Name |
        Format-Table -Wrap -AutoSize
}

$pluginGuids = @(Get-PluginGuids -Events $events)
$serverMods = @(Get-ServerModNames -Events $events)
Write-Host "Snapshot"
[pscustomobject]@{
    BepInExPlugins = $pluginGuids.Count
    ServerModFolders = $serverMods.Count
} | Format-List

if ($ComparePrevious) {
    $current = Get-Item -LiteralPath $Path
    $previous = Get-ChildItem -LiteralPath $diagnosticsDir -File -Filter "client-*.jsonl" -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -ne $current.FullName -and $_.LastWriteTime -lt $current.LastWriteTime } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if ($null -eq $previous) {
        Write-Host "No previous diagnostics file available for comparison."
    } else {
        $previousEvents = @(Read-DiagnosticsEvents -FilePath $previous.FullName)
        $previousPlugins = @(Get-PluginGuids -Events $previousEvents)
        $previousServerMods = @(Get-ServerModNames -Events $previousEvents)

        Write-Host "Compared with: $($previous.FullName)"
        Write-Host "Added BepInEx plugins"
        Compare-Object -ReferenceObject $previousPlugins -DifferenceObject $pluginGuids |
            Where-Object { $_.SideIndicator -eq "=>" } |
            Select-Object -ExpandProperty InputObject

        Write-Host "Removed BepInEx plugins"
        Compare-Object -ReferenceObject $previousPlugins -DifferenceObject $pluginGuids |
            Where-Object { $_.SideIndicator -eq "<=" } |
            Select-Object -ExpandProperty InputObject

        Write-Host "Added server mod folders"
        Compare-Object -ReferenceObject $previousServerMods -DifferenceObject $serverMods |
            Where-Object { $_.SideIndicator -eq "=>" } |
            Select-Object -ExpandProperty InputObject

        Write-Host "Removed server mod folders"
        Compare-Object -ReferenceObject $previousServerMods -DifferenceObject $serverMods |
            Where-Object { $_.SideIndicator -eq "<=" } |
            Select-Object -ExpandProperty InputObject
    }
}
