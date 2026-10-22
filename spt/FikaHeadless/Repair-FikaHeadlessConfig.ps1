# SPDX-License-Identifier: MIT
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string] $MainSptRoot,
    [Parameter(Mandatory)][string] $HeadlessRoot,
    [Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9_-]{1,128}$')][string] $ProfileId,
    [Parameter(Mandatory)][uri] $BackendUrl,
    [string] $ForceIp = 'Disabled',
    [string] $BindIp = 'Disabled',
    [ValidateRange(1,65535)][int] $UdpPort = 25565,
    [switch] $Apply
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'FikaHeadless.Common.ps1')
$main = Get-SafeDirectory -Path $MainSptRoot -MustExist
$headless = Get-SafeDirectory -Path $HeadlessRoot -MustExist
Assert-SeparateDirectories $main $headless
Assert-IpSetting $ForceIp
Assert-IpSetting $BindIp
if (-not $BackendUrl.IsAbsoluteUri -or $BackendUrl.Scheme -notin 'http','https' -or $BackendUrl.UserInfo) {
    throw 'BackendUrl must be an absolute HTTP(S) URL without embedded credentials.'
}
$fikaConfig = Join-Path $headless 'BepInEx\config\com.fika.core.cfg'
$launchConfig = Join-Path $headless 'HeadlessConfig.json'
$serverConfig = Join-Path $main "SPT\user\mods\fika-server\assets\scripts\$ProfileId\HeadlessConfig.json"
$profileDirectory = Join-Path $main 'SPT\user\profiles'
$null = Get-SafeDirectory -Path $profileDirectory -MustExist
$profileFile = Join-Path $profileDirectory ($ProfileId + '.json')
Assert-SafeFile $profileFile
if (-not (Test-Path -LiteralPath $profileFile -PathType Leaf)) { throw 'The explicitly selected profile must already exist in SPT/user/profiles.' }
foreach ($file in @($fikaConfig, $launchConfig, $serverConfig)) { Assert-SafeFile $file }
if (-not (Test-Path -LiteralPath $fikaConfig -PathType Leaf)) { throw 'Headless Fika configuration does not exist. Complete installer first.' }
$text = Get-Content -LiteralPath $fikaConfig -Raw
$settings = [ordered]@{ 'Force IP' = $ForceIp; 'Force Bind IP' = $BindIp; 'UDP Port' = $UdpPort }
foreach ($key in $settings.Keys) {
    $pattern = '(?m)^' + [regex]::Escape($key) + ' = [^\r\n]*'
    if ([regex]::Matches($text, $pattern).Count -ne 1) { throw "Expected exactly one '$key' setting; no changes made." }
    $replacement = $key + ' = ' + $settings[$key]
    $text = [regex]::Replace($text, $pattern, [System.Text.RegularExpressions.MatchEvaluator] { param($match) $replacement }.GetNewClosure())
}
$backupRoot = Join-Path $headless ('_outlands_backups\' + [guid]::NewGuid().ToString('N'))
$null = Get-SafeDirectory $backupRoot
if (-not $Apply) {
    Write-Output 'Preview: back up existing Fika/launch/server configs, write the selected launch profile and endpoint to both launch configs, update three network settings. No files changed.'
    return
}
if ($PSCmdlet.ShouldProcess("$headless and selected Fika launch config in $main", 'Back up and repair Fika headless settings')) {
    New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
    $backups = @()
    $index = 0
    foreach ($file in @($fikaConfig, $launchConfig, $serverConfig)) {
        $backup = Join-Path $backupRoot (([string]$index) + '-' + [IO.Path]::GetFileName($file))
        $existed = Test-Path -LiteralPath $file -PathType Leaf
        if ($existed) { Copy-Item -LiteralPath $file -Destination $backup }
        $backups += [pscustomobject]@{ Original = $file; Existed = $existed; Backup = $(if ($existed) { $backup } else { $null }) }
        $index++
    }
    $backups | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $backupRoot 'manifest.json') -Encoding utf8
    $json = [pscustomobject]@{ ProfileId = $ProfileId; BackendUrl = $BackendUrl.AbsoluteUri.TrimEnd('/'); StartMinimized = $false } | ConvertTo-Json
    New-Item -ItemType Directory -Path (Split-Path -Parent $serverConfig) -Force | Out-Null
    $json | Set-Content -LiteralPath $launchConfig -Encoding utf8
    $json | Set-Content -LiteralPath $serverConfig -Encoding utf8
    Set-Content -LiteralPath $fikaConfig -Value $text -NoNewline -Encoding utf8
    Write-Output "Repaired. Backups and original-path manifest: $backupRoot"
}
