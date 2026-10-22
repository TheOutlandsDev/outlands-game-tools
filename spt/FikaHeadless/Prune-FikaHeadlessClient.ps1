# SPDX-License-Identifier: MIT
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string] $HeadlessRoot,
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string[]] $PluginName,
    [switch] $Apply
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'FikaHeadless.Common.ps1')
$headless = Get-SafeDirectory -Path $HeadlessRoot -MustExist
$plugins = Get-SafeDirectory -Path (Join-Path $headless 'BepInEx\plugins') -MustExist
$disabled = Get-SafeDirectory -Path (Join-Path $headless ('_outlands_disabled\' + [guid]::NewGuid().ToString('N')))
$moves = @()
foreach ($name in $PluginName | Select-Object -Unique) {
    if ($name -notmatch '^[A-Za-z0-9][A-Za-z0-9._ -]*$' -or $name -in '.', '..') { throw "PluginName must be a direct child name, not a path: $name" }
    $source = Join-Path $plugins $name
    if (-not (Test-Path -LiteralPath $source)) { throw "Plugin not found; no changes made: $name" }
    $item = Get-Item -LiteralPath $source -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Linked plugin entries are unsupported: $name" }
    $moves += [pscustomobject]@{ Source = $source; Destination = (Join-Path $disabled $name) }
}
if (-not $Apply) {
    $moves | ForEach-Object { Write-Output "Preview: move $($_.Source) to $($_.Destination)" }
    return
}
if ($PSCmdlet.ShouldProcess($headless, 'Move explicitly named plugins into a new disabled folder')) {
    New-Item -ItemType Directory -Path $disabled | Out-Null
    $manifestPath = Join-Path $disabled 'moves.json'
    @($moves) | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifestPath -Encoding utf8
    foreach ($move in $moves) { Move-Item -LiteralPath $move.Source -Destination $move.Destination }
    Write-Output "Moved $($moves.Count) entries. Restore their original locations using $manifestPath while all game processes are stopped."
}
