$ErrorActionPreference = 'Stop'
$moduleRoot = Split-Path -Parent $PSScriptRoot
$testRoot = Join-Path $moduleRoot ('.validation\summary-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
try {
    $capture = Join-Path $testRoot 'raid-synthetic.jsonl'
    @(
        '{"type":"raid_start","payload":{"map":"synthetic-map"}}'
        '{"type":"snapshot","payload":{"raid_seconds":5,"player_count":2,"bot_count":1,"tracking":{"active_count":1},"line_of_sight":[{"main_can_see_bot":true}]}}'
        '{"type":"snapshot","payload":{"raid_seconds":10,"player_count":4,"bot_count":3,"tracking":{"active_count":3},"line_of_sight":[]}}'
        '{"type":"tracking_assigned","payload":{}}'
        '{"type":"raid_end","payload":{"raid_seconds":12,"dropped_lines":2}}'
        'invalid-json'
    ) | Set-Content -LiteralPath $capture -Encoding UTF8
    $script = Join-Path $moduleRoot 'Summarize-QuakeBrainTelemetry.ps1'
    $report = & $script -Path $capture 6>&1 | Out-String -Width 240
    foreach ($pattern in @('AvgPlayers\s*:\s*3', 'AvgBots\s*:\s*2', 'MaxTrackedActive\s*:\s*3', 'LineOfSightSamples\s*:\s*1', 'VisibleLineOfSight\s*:\s*1', 'DroppedLines\s*:\s*2', 'ParseErrors\s*:\s*1', 'RaidSeconds\s*:\s*12')) {
        if ($report -notmatch $pattern) { throw "Missing expected report value: $pattern`n$report" }
    }
    $latest = & $script -TelemetryDirectory $testRoot -Latest 1 6>&1 | Out-String -Width 240
    if ($latest -notmatch 'raid-synthetic.jsonl') { throw 'Directory selection failed.' }
    Write-Output 'PASS: telemetry averages, tracking maximum, visibility counts, dropped lines, malformed JSON, and directory selection.'
} finally {
    $resolvedTest = [IO.Path]::GetFullPath($testRoot)
    $allowedRoot = [IO.Path]::GetFullPath((Join-Path $moduleRoot '.validation')) + [IO.Path]::DirectorySeparatorChar
    if (-not $resolvedTest.StartsWith($allowedRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Refusing cleanup outside module validation directory.' }
    Remove-Item -LiteralPath $resolvedTest -Recurse -Force
}
