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
    [switch] $IncludeMainClient,
    [switch] $Apply
)
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'This helper supports local Windows filesystems only.' }
. (Join-Path $PSScriptRoot 'FikaHeadless.Common.ps1')
. (Join-Path $PSScriptRoot 'FikaRepair.Engine.ps1')
$plan = Get-RepairPlan $MainSptRoot $HeadlessRoot $ProfileId $BackendUrl $ForceIp $BindIp $UdpPort $IncludeMainClient.IsPresent
Write-Output ('Preview: {0} selected configurations; {1} differ or are new.' -f $plan.Entries.Count, @($plan.Entries | Where-Object { -not $_.Existed -or $_.BeforeHash -ne $_.AfterHash }).Count)
foreach ($entry in $plan.Entries) { Write-Output ("  {0}: {1}; existed={2}; SHA256 {3} -> {4}" -f $entry.Root, $entry.Relative, $entry.Existed, $entry.BeforeHash, $entry.AfterHash) }
if (-not $Apply) { Write-Output 'No files changed. Stop all related processes and review before repeating with -Apply.'; return }
if ($PSCmdlet.ShouldProcess('Selected local SPT/headless configuration files', 'Back up, verify and repair')) {
    $backup = Invoke-RepairPlan $plan
    Write-Output "Repaired and verified. Keep this recovery directory private: $backup"
}
