param(
    [string] $TelemetryDirectory,
    [string] $Path = "",
    [int] $Latest = 1
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Path) -and [string]::IsNullOrWhiteSpace($TelemetryDirectory)) {
    throw 'Provide -Path to a JSONL file or -TelemetryDirectory to a capture directory.'
}

if ([string]::IsNullOrWhiteSpace($Path)) {
    $files = Get-ChildItem -LiteralPath $TelemetryDirectory -Filter "raid-*.jsonl" -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First ([Math]::Max(1, $Latest))
} else {
    $files = @(Get-Item -LiteralPath $Path)
}

if (-not $files -or $files.Count -eq 0) {
    Write-Host "No QuakeBrain telemetry files found in $TelemetryDirectory"
    exit 0
}

foreach ($file in $files) {
    $eventCounts = @{}
    $snapshotCount = 0
    $botSamples = 0
    $maxBots = 0
    $playerSamples = 0
    $maxPlayers = 0
    $losSamples = 0
    $visibleLos = 0
    $trackingSamples = 0
    $trackedActiveTotal = 0
    $trackedActiveMax = 0
    $map = ""
    $raidSeconds = 0
    $droppedLines = 0
    $parseErrors = 0

    foreach ($line in Get-Content -LiteralPath $file.FullName) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        try {
            $entry = $line | ConvertFrom-Json
        } catch {
            $parseErrors++
            continue
        }

        if (-not $eventCounts.ContainsKey($entry.type)) {
            $eventCounts[$entry.type] = 0
        }
        $eventCounts[$entry.type]++

        if ($entry.payload.map) {
            $map = [string]$entry.payload.map
        }

        if ($entry.payload.raid_seconds -ne $null) {
            $raidSeconds = [double]$entry.payload.raid_seconds
        }

        if ($entry.type -eq "snapshot") {
            $snapshotCount++
            $playerCount = [int]$entry.payload.player_count
            $botCount = [int]$entry.payload.bot_count
            $playerSamples += $playerCount
            $botSamples += $botCount
            $maxPlayers = [Math]::Max($maxPlayers, $playerCount)
            $maxBots = [Math]::Max($maxBots, $botCount)

            foreach ($los in @($entry.payload.line_of_sight)) {
                $losSamples++
                if ($los.main_can_see_bot -eq $true) {
                    $visibleLos++
                }
            }

            if ($entry.payload.tracking -ne $null) {
                $trackingSamples++
                $activeTracked = [int]$entry.payload.tracking.active_count
                $trackedActiveTotal += $activeTracked
                $trackedActiveMax = [Math]::Max($trackedActiveMax, $activeTracked)
            }
        }

        if ($entry.type -eq "raid_end" -and $entry.payload.dropped_lines -ne $null) {
            $droppedLines = [int]$entry.payload.dropped_lines
        }
    }

    [pscustomobject]@{
        File = $file.Name
        Map = $map
        RaidSeconds = [Math]::Round($raidSeconds, 1)
        Events = ($eventCounts.GetEnumerator() | Sort-Object Name | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join ", "
        Snapshots = $snapshotCount
        AvgPlayers = if ($snapshotCount -gt 0) { [Math]::Round($playerSamples / $snapshotCount, 2) } else { 0 }
        MaxPlayers = $maxPlayers
        AvgBots = if ($snapshotCount -gt 0) { [Math]::Round($botSamples / $snapshotCount, 2) } else { 0 }
        MaxBots = $maxBots
        AvgTrackedActive = if ($trackingSamples -gt 0) { [Math]::Round($trackedActiveTotal / $trackingSamples, 2) } else { 0 }
        MaxTrackedActive = $trackedActiveMax
        TrackingAssignments = if ($eventCounts.ContainsKey("tracking_assigned")) { $eventCounts["tracking_assigned"] } else { 0 }
        LineOfSightSamples = $losSamples
        VisibleLineOfSight = $visibleLos
        DroppedLines = $droppedLines
        ParseErrors = $parseErrors
        SizeKb = [Math]::Round($file.Length / 1kb, 1)
        LastWriteTime = $file.LastWriteTime
    } | Format-List
}
