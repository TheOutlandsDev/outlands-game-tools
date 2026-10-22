param(
    [Parameter(Mandatory)][string] $GameRoot,
    [string] $OutputDirectory = (Join-Path $PSScriptRoot 'artifacts\ScavLifeFramework'),
    [switch] $NoRestore
)

$ErrorActionPreference = 'Stop'
$GameRoot = (Resolve-Path -LiteralPath $GameRoot).Path
$project = Join-Path $PSScriptRoot 'src\Codex.ScavLifeFramework\Codex.ScavLifeFramework.csproj'
$buildArgs = @('build', $project, '-c', 'Release', "-p:GameRoot=$GameRoot")
if ($NoRestore) { $buildArgs += '--no-restore' }
& dotnet @buildArgs
if ($LASTEXITCODE -ne 0) { throw "Build failed with exit code $LASTEXITCODE." }

# Package only this project's output. This script never installs into the game.
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'src\Codex.ScavLifeFramework\bin\Release\net9.0\Codex.ScavLifeFramework.dll') -Destination $OutputDirectory -Force

$configDir = Join-Path $OutputDirectory 'config'
New-Item -ItemType Directory -Force -Path $configDir | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'config\config.json') -Destination $configDir -Force

Write-Host "Built Codex.ScavLifeFramework.dll into $OutputDirectory"
