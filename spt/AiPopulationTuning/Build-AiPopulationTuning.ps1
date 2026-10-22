# SPDX-License-Identifier: MIT
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string] $SptServerDirectory,
    [ValidateSet('Debug', 'Release')][string] $Configuration = 'Release'
)
$ErrorActionPreference = 'Stop'
$serverDirectory = (Resolve-Path -LiteralPath $SptServerDirectory).Path
$project = Join-Path $PSScriptRoot 'src\Codex.AiPopulationTuning\Codex.AiPopulationTuning.csproj'
& dotnet build $project -c $Configuration "-p:SptServerDirectory=$serverDirectory" --configfile (Join-Path $PSScriptRoot 'NuGet.Config') -p:NuGetAudit=false
if ($LASTEXITCODE -ne 0) { throw "Build failed with exit code $LASTEXITCODE." }
Write-Host 'Build only. See README.md for manual installation.'
