# SPDX-License-Identifier: MIT
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string] $MainSptRoot,
    [Parameter(Mandatory)][string] $HeadlessRoot,
    [Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9_-]{1,128}$')][string] $ProfileId,
    [switch] $Apply
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'FikaHeadless.Common.ps1')
$main = Get-SafeDirectory -Path $MainSptRoot -MustExist
$headless = Get-SafeDirectory -Path $HeadlessRoot
Assert-SeparateDirectories $main $headless
if (Test-Path -LiteralPath $headless) { throw 'HeadlessRoot must not already exist; this wrapper does not overwrite installations.' }
$installer = Join-Path $main 'Fika-Installer.exe'
if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) { throw 'Obtain the compatible Fika installer separately and place it in MainSptRoot.' }
Assert-SafeFile $installer
$arguments = @('install', 'headless', '--path', $main, '--method', 'HardCopy', '--profileId', $ProfileId)
if (-not $Apply) {
    Write-Output "Preview: create $headless, copy the local Fika installer, then run install headless with HardCopy and the supplied profile. No files changed."
    return
}
if ($PSCmdlet.ShouldProcess($headless, 'Create headless client using the separately installed Fika installer')) {
    New-Item -ItemType Directory -Path $headless | Out-Null
    $localInstaller = Join-Path $headless 'Fika-Installer.exe'
    Copy-Item -LiteralPath $installer -Destination $localInstaller
    Push-Location -LiteralPath $headless
    try {
        & $localInstaller @arguments
        if ($LASTEXITCODE -ne 0) { throw "Fika installer failed with exit code $LASTEXITCODE; inspect the new directory before retrying." }
    } finally { Pop-Location }
    Write-Output 'Installer completed. Review the new client and run Repair-FikaHeadlessConfig.ps1 separately if configuration changes are needed.'
}
