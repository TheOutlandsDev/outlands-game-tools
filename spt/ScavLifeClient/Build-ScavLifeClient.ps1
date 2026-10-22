param(
    [Parameter(Mandatory)][string] $GameRoot,
    [string] $OutputDirectory = (Join-Path $PSScriptRoot 'artifacts\ScavLifeClient'),
    [switch] $NoRestore
)

$ErrorActionPreference = 'Stop'
$GameRoot = (Resolve-Path -LiteralPath $GameRoot).Path
$project = Join-Path $PSScriptRoot 'src\Codex.ScavLife.Client\Codex.ScavLife.Client.csproj'
$buildArgs = @('build', $project, '-c', 'Release', "-p:GameRoot=$GameRoot")
if ($NoRestore) { $buildArgs += '--no-restore' }
& dotnet @buildArgs
if ($LASTEXITCODE -ne 0) { throw "Build failed with exit code $LASTEXITCODE." }

# Package only this project's output. This script never installs into the game.
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'src\Codex.ScavLife.Client\bin\Release\Codex.ScavLife.Client.dll') -Destination $OutputDirectory -Force

Write-Host "Built Codex.ScavLife.Client.dll into $OutputDirectory"
