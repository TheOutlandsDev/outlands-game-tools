# SPDX-License-Identifier: MIT
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string] $MainSptRoot,
    [Parameter(Mandatory)][string] $HeadlessRoot,
    [Parameter(Mandatory)][string] $BackupDirectory,
    [switch] $Apply
)
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'This helper supports local Windows filesystems only.' }
. (Join-Path $PSScriptRoot 'FikaHeadless.Common.ps1')
. (Join-Path $PSScriptRoot 'FikaRepair.Engine.ps1')
$entries = @(Get-RestorePlan $BackupDirectory $MainSptRoot $HeadlessRoot)
Write-Output ('Preview: restore original bytes for {0} files; remove up to {1} exact repaired files that did not originally exist.' -f @($entries | Where-Object Existed).Count, @($entries | Where-Object { -not $_.Existed -and $_.CurrentExists }).Count)
if (-not $Apply) { Write-Output 'No files changed. Keep related processes stopped; repeat with -Apply to restore.'; return }
if ($PSCmdlet.ShouldProcess('Selected local configurations described by the verified backup', 'Restore originals and remove exact newly created files')) {
    Invoke-RepairRestore $entries
    Write-Output 'Restored and verified. Recovery files retained; empty directories may remain.'
}
