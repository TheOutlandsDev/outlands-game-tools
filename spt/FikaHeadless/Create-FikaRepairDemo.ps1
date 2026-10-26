# SPDX-License-Identifier: MIT
[CmdletBinding()]
param([Parameter(Mandatory)][string] $Destination)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'FikaHeadless.Common.ps1')
$root = Get-SafeDirectory $Destination
if (Test-Path -LiteralPath $root) { throw 'Demo destination must not already exist.' }
$null = New-Item -ItemType Directory -Path $root
$utf8 = New-Object Text.UTF8Encoding($false)
$files = [ordered]@{
    'Main\SPT\user\profiles\demo_headless.json' = '{"fictional":true}'
    'Headless\HeadlessConfig.json' = '{"ProfileId":"demo_headless","BackendUrl":"https://example.invalid:6969","StartMinimized":true,"FictionalNote":"keep this setting"}'
    'Headless\BepInEx\config\com.fika.core.cfg' = "[Fictional Network]`r`nForce IP = Disabled`r`nForce Bind IP = Disabled`r`nUDP Port = 1`r`nOther = keep`r`n"
    'Main\BepInEx\config\com.fika.core.cfg' = "Force IP = Disabled`nForce Bind IP = Disabled`nUDP Port = 1`n"
}
foreach ($relative in $files.Keys) {
    $path = Join-Path $root $relative
    $null = New-Item -ItemType Directory -Path (Split-Path -Parent $path) -Force
    [IO.File]::WriteAllText($path, $files[$relative], $utf8)
}
Write-Output "Fictional demo created: $root"
Write-Output 'No game, profile discovery, installer, network request or repair was run. See README.md for preview/apply/restore commands.'
