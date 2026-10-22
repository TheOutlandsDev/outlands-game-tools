$ErrorActionPreference = 'Stop'
$moduleRoot = Split-Path -Parent $PSScriptRoot
$testRoot = Join-Path $moduleRoot ('.validation\summary-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
try {
    $current = Join-Path $testRoot 'client-current.jsonl'
    $previous = Join-Path $testRoot 'client-previous.jsonl'
    @(
        '{"type":"session_start","payload":{"label":"synthetic"}}'
        '{"type":"performance_sample","payload":{"fps":50,"max_frame_ms":40,"hitch_count":1}}'
        '{"type":"performance_sample","payload":{"fps":70,"max_frame_ms":80,"hitch_count":2}}'
        '{"type":"bepinex_plugins","payload":{"plugins":[]}}'
        '{"type":"server_mod_folders","payload":{"entries":[]}}'
        'invalid-json'
    ) | Set-Content -LiteralPath $current -Encoding UTF8
    @(
        '{"type":"bepinex_plugins","payload":{"plugins":[]}}'
        '{"type":"server_mod_folders","payload":{"entries":[]}}'
    ) | Set-Content -LiteralPath $previous -Encoding UTF8
    (Get-Item -LiteralPath $previous).LastWriteTime = (Get-Date).AddMinutes(-1)
    $script = Join-Path $moduleRoot 'Summarize-CodexDiagnostics.ps1'
    $report = & $script -Path $current -ComparePrevious 6>&1 | Out-String -Width 240
    foreach ($pattern in @('AvgFps\s*:\s*60', 'WorstFrameMs\s*:\s*80', 'SampleHitches\s*:\s*3', 'parse_error', 'Compared with:')) {
        if ($report -notmatch $pattern) { throw "Missing expected report value: $pattern`n$report" }
    }
    $latest = & $script -DiagnosticsDirectory $testRoot 6>&1 | Out-String -Width 240
    if ($latest -notmatch 'client-current.jsonl') { throw 'Latest-file selection failed.' }
    Write-Output 'PASS: diagnostics averages, maxima, hitch totals, malformed JSON, empty comparison sets, and latest-file selection.'
} finally {
    $resolvedTest = [IO.Path]::GetFullPath($testRoot)
    $allowedRoot = [IO.Path]::GetFullPath((Join-Path $moduleRoot '.validation')) + [IO.Path]::DirectorySeparatorChar
    if (-not $resolvedTest.StartsWith($allowedRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Refusing cleanup outside module validation directory.' }
    Remove-Item -LiteralPath $resolvedTest -Recurse -Force
}
