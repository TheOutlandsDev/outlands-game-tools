[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $GameRoot,
    [string] $InstallDirectory
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$gamePath = (Resolve-Path -LiteralPath $GameRoot).ProviderPath
if (-not (Test-Path -LiteralPath (Join-Path $gamePath 'BepInEx\core\BepInEx.dll') -PathType Leaf)) {
    throw 'GameRoot does not contain the required installed SPT/BepInEx references.'
}
$project = Join-Path $root 'src\Codex.Diagnostics.Client\Codex.Diagnostics.Client.csproj'

# nuget.config clears network feeds. All game/mod references stay in GameRoot.
& dotnet build $project -c Release "-p:GameRoot=$gamePath" --configfile (Join-Path $root 'nuget.config') --disable-build-servers
if ($LASTEXITCODE -ne 0) {
    throw "Build failed with exit code $LASTEXITCODE."
}
$outputDll = Join-Path $root 'src\Codex.Diagnostics.Client\bin\Release\Codex.Diagnostics.Client.dll'
if (-not (Test-Path -LiteralPath $outputDll -PathType Leaf)) {
    throw "Build output is missing: $outputDll"
}
Write-Host "Built $outputDll"

# Building is local only. Installation requires an explicit destination.
if (-not [string]::IsNullOrWhiteSpace($InstallDirectory)) {
    New-Item -ItemType Directory -Path $InstallDirectory -Force | Out-Null
    Copy-Item -LiteralPath $outputDll -Destination (Join-Path $InstallDirectory 'Codex.Diagnostics.Client.dll') -Force
    Write-Host "Installed Codex.Diagnostics.Client.dll to $InstallDirectory"
}
