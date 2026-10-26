# SPDX-License-Identifier: MIT
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$fixture = Join-Path $PSScriptRoot ('.test-work-' + [guid]::NewGuid().ToString('N'))
$main = Join-Path $fixture 'Main'
$headless = Join-Path $fixture 'Headless'
$profile = 'synthetic_headless_profile'
$repair = Join-Path $PSScriptRoot 'Repair-FikaHeadlessConfig.ps1'
$prune = Join-Path $PSScriptRoot 'Prune-FikaHeadlessClient.ps1'
function Assert-True { param([bool] $Value, [string] $Message); if (-not $Value) { throw $Message } }
function Assert-Throws { param([scriptblock] $Action); $thrown = $false; try { & $Action | Out-Null } catch { $thrown = $true }; Assert-True $thrown 'Expected an input rejection.' }
function Get-FixtureSnapshot {
    return @(Get-ChildItem -LiteralPath $fixture -Recurse -File | Sort-Object FullName | ForEach-Object {
        $_.FullName.Substring($fixture.Length) + ':' + (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    }) -join "`n"
}
try {
    foreach ($directory in @((Join-Path $main 'SPT\user\profiles'), (Join-Path $headless 'BepInEx\config'), (Join-Path $headless 'BepInEx\plugins'))) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }
    Set-Content -LiteralPath (Join-Path $main "SPT\user\profiles\$profile.json") -Value '{"synthetic":true}'
    Set-Content -LiteralPath (Join-Path $main 'Fika-Installer.exe') -Value 'synthetic text fixture; must never execute'
    $newHeadless = Join-Path $fixture 'NewHeadless'
    & (Join-Path $PSScriptRoot 'Install-FikaHeadless.ps1') -MainSptRoot $main -HeadlessRoot $newHeadless -ProfileId $profile | Out-Null
    & (Join-Path $PSScriptRoot 'Install-FikaHeadless.ps1') -MainSptRoot $main -HeadlessRoot $newHeadless -ProfileId $profile -Apply -WhatIf | Out-Null
    Assert-True (-not (Test-Path -LiteralPath $newHeadless)) 'Installer preview/WhatIf created an installation.'
    $configPath = Join-Path $headless 'BepInEx\config\com.fika.core.cfg'
    $original = "Force IP = Disabled`r`nForce Bind IP = Disabled`r`nUDP Port = 1`r`nOther = keep`r`n"
    Set-Content -LiteralPath $configPath -Value $original -NoNewline
    $originalHash = (Get-FileHash -LiteralPath $configPath).Hash
    $argsForRepair = @{ MainSptRoot = $main; HeadlessRoot = $headless; ProfileId = $profile; BackendUrl = 'https://127.0.0.1:6969'; ForceIp = '192.0.2.1'; BindIp = 'Disabled'; UdpPort = 25565 }
    $before = Get-FixtureSnapshot
    & $repair @argsForRepair | Out-Null
    & $repair @argsForRepair -Apply -WhatIf | Out-Null
    Assert-True ((Get-FixtureSnapshot) -eq $before) 'Preview/WhatIf changed fixture files.'
    & $repair @argsForRepair -Apply -Confirm:$false | Out-Null
    $current = Get-Content -LiteralPath $configPath -Raw
    Assert-True ($current.Contains('Force IP = 192.0.2.1') -and $current.Contains('UDP Port = 25565') -and $current.Contains('Other = keep')) 'Network edit lost or failed settings.'
    $launch = Get-Content -LiteralPath (Join-Path $headless 'HeadlessConfig.json') -Raw | ConvertFrom-Json
    Assert-True ($launch.ProfileId -eq $profile -and $launch.BackendUrl -eq 'https://127.0.0.1:6969') 'Launch config mismatch.'
    $serverLaunch = Join-Path $main "SPT\user\mods\fika-server\assets\scripts\$profile\HeadlessConfig.json"
    Assert-True ((Get-FileHash -LiteralPath $serverLaunch).Hash -eq (Get-FileHash -LiteralPath (Join-Path $headless 'HeadlessConfig.json')).Hash) 'Server launch differs.'
    $backup = @(Get-ChildItem -LiteralPath (Join-Path $headless '_outlands_backups') -Recurse -File -Filter '0.original')
    Assert-True ($backup.Count -eq 1 -and (Get-FileHash -LiteralPath $backup[0].FullName).Hash -eq $originalHash) 'Backup does not preserve original bytes.'
    $plugin = Join-Path $headless 'BepInEx\plugins\SyntheticPlugin.dll'
    Set-Content -LiteralPath $plugin -Value 'synthetic text fixture, not a DLL'
    $before = Get-FixtureSnapshot
    & $prune -HeadlessRoot $headless -PluginName 'SyntheticPlugin.dll' | Out-Null
    & $prune -HeadlessRoot $headless -PluginName 'SyntheticPlugin.dll' -Apply -WhatIf | Out-Null
    Assert-True ((Get-FixtureSnapshot) -eq $before) 'Prune preview/WhatIf changed files.'
    Assert-Throws { & $prune -HeadlessRoot $headless -PluginName '..\escape' -Apply }
    & $prune -HeadlessRoot $headless -PluginName 'SyntheticPlugin.dll' -Apply -Confirm:$false | Out-Null
    Assert-True (-not (Test-Path -LiteralPath $plugin)) 'Selected plugin was not moved.'
    Assert-True (@(Get-ChildItem -LiteralPath (Join-Path $headless '_outlands_disabled') -Recurse -File -Filter 'SyntheticPlugin.dll').Count -eq 1) 'Disabled plugin missing.'
    $invalid = $argsForRepair.Clone(); $invalid.ProfileId = '..\escape'
    Assert-Throws { & $repair @invalid -Apply }
    $invalid = $argsForRepair.Clone(); $invalid.BackendUrl = 'file:///C:/fake'
    Assert-Throws { & $repair @invalid -Apply }
    $invalid = $argsForRepair.Clone(); $invalid.HeadlessRoot = $main
    Assert-Throws { & $repair @invalid -Apply }
    Add-Content -LiteralPath $configPath -Value 'UDP Port = 2'
    $before = Get-FixtureSnapshot
    Assert-Throws { & $repair @argsForRepair -Apply }
    Assert-True ((Get-FixtureSnapshot) -eq $before) 'Rejected duplicate setting changed files.'
    Write-Output 'PASS: installer/config/prune previews, WhatIf, config edits/backups, selected moves, traversal/URL/overlap/duplicate rejection.'
} finally {
    $full = [IO.Path]::GetFullPath($fixture)
    $safeParent = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\') + '\'
    if ($full.StartsWith($safeParent, [StringComparison]::OrdinalIgnoreCase) -and (Split-Path -Leaf $full).StartsWith('.test-work-')) {
        if (Test-Path -LiteralPath $full) { Remove-Item -LiteralPath $full -Recurse -Force }
    } else { throw 'Refusing unexpected fixture cleanup path.' }
}
