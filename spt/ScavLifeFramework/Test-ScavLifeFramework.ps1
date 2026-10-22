param(
    [switch] $AllowStateChanges,
    [string] $BaseUrl = "https://127.0.0.1:6969",
    [string] $ProfileId = "local-test"
)

$ErrorActionPreference = "Stop"

if (-not $AllowStateChanges) { throw "This script mutates Scav Life state. Use -AllowStateChanges with a backed-up test profile." }
$backendUri = [Uri]$BaseUrl
$backendAddress = $null
if (-not [Net.IPAddress]::TryParse($backendUri.DnsSafeHost, [ref]$backendAddress) -or -not [Net.IPAddress]::IsLoopback($backendAddress) -or $backendUri.Scheme -notin @("http", "https") -or $backendUri.UserInfo -or $backendUri.Query -or $backendUri.Fragment -or $backendUri.AbsolutePath -ne "/") { throw "BaseUrl must be a loopback IP HTTP(S) origin." }
$BaseUrl = $backendUri.GetLeftPart([UriPartial]::Authority)

if (-not ("System.IO.Compression.ZLibStream" -as [type])) {
    throw "This tester requires PowerShell 7+ because SPT uses zlib request/response bodies. Run it with pwsh, not Windows PowerShell."
}

function ConvertTo-ZlibBytes {
    param([string] $Text)

    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
    $output = [System.IO.MemoryStream]::new()
    $zlibStream = [System.IO.Compression.ZLibStream]::new($output, [System.IO.Compression.CompressionLevel]::Optimal, $true)
    $zlibStream.Write($bytes, 0, $bytes.Length)
    $zlibStream.Dispose()
    $result = $output.ToArray()
    $output.Dispose()
    return $result
}

function ConvertFrom-ZlibBytes {
    param([byte[]] $Bytes)

    $inputStream = [System.IO.MemoryStream]::new($Bytes)
    $zlibStream = [System.IO.Compression.ZLibStream]::new($inputStream, [System.IO.Compression.CompressionMode]::Decompress)
    $reader = [System.IO.StreamReader]::new($zlibStream, [System.Text.Encoding]::UTF8)
    $text = $reader.ReadToEnd()
    $reader.Dispose()
    $inputStream.Dispose()
    return $text
}

function Invoke-ScavLifeRoute {
    param(
        [string] $Path,
        [object] $Body
    )

    $json = $Body | ConvertTo-Json -Depth 8
    $bodyBytes = ConvertTo-ZlibBytes $json

    $handler = [System.Net.Http.HttpClientHandler]::new()
    $handler.AllowAutoRedirect = $false
    $client = [System.Net.Http.HttpClient]::new($handler)
    $content = [System.Net.Http.ByteArrayContent]::new($bodyBytes)
    $content.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse("application/json")
    $response = $client.PostAsync("$BaseUrl$Path", $content).GetAwaiter().GetResult()
    $response.EnsureSuccessStatusCode() | Out-Null
    $bytes = $response.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult()
    $client.Dispose()

    $text = ConvertFrom-ZlibBytes $bytes

    $text | ConvertFrom-Json
}

Write-Host "Reset"
Invoke-ScavLifeRoute "/singleplayer/scavlife/debug/reset" @{ profileId = $ProfileId } | ConvertTo-Json -Depth 12

Write-Host "Status"
Invoke-ScavLifeRoute "/singleplayer/scavlife/status" @{ profileId = $ProfileId } | ConvertTo-Json -Depth 12

Write-Host "Dossier"
Invoke-ScavLifeRoute "/singleplayer/scavlife/dossier" @{ profileId = $ProfileId } | ConvertTo-Json -Depth 12

Write-Host "Raid plan"
Invoke-ScavLifeRoute "/singleplayer/scavlife/raid-plan" @{
    profileId = $ProfileId
    location = "tarkovstreets"
} | ConvertTo-Json -Depth 12

Write-Host "Stash status"
Invoke-ScavLifeRoute "/singleplayer/scavlife/stash/status" @{ profileId = $ProfileId } | ConvertTo-Json -Depth 12

Write-Host "Customization options"
Invoke-ScavLifeRoute "/singleplayer/scavlife/customization/options" @{ profileId = $ProfileId } | ConvertTo-Json -Depth 12

Write-Host "Apply custom scav identity"
Invoke-ScavLifeRoute "/singleplayer/scavlife/customization/apply" @{
    profileId = $ProfileId
    nickname = "Local Runner"
    archetype = "courier"
    homeMap = "tarkovstreets"
    temperament = "cautious"
    voice = "quiet"
    outfitPreset = "scrapper"
    tags = @("local", "persistent", "transit-ready")
    kitPreferences = @{
        primaryWeapon = "smg"
        armor = "light"
        backpack = "small-pack"
        medical = "balanced"
        lootFocus = "hardware"
    }
} | ConvertTo-Json -Depth 12

Write-Host "Randomize custom scav identity"
Invoke-ScavLifeRoute "/singleplayer/scavlife/customization/randomize" @{
    profileId = $ProfileId
} | ConvertTo-Json -Depth 12

Write-Host "Complete survived test run"
Invoke-ScavLifeRoute "/singleplayer/scavlife/debug/complete-run" @{
    profileId = $ProfileId
    survived = $true
    location = "factory4_day"
    lootValue = 25000
    itemsExtracted = 3
    kills = 1
} | ConvertTo-Json -Depth 12

Write-Host "Raid plan after survived run"
Invoke-ScavLifeRoute "/singleplayer/scavlife/raid-plan" @{
    profileId = $ProfileId
    location = "factory4_day"
} | ConvertTo-Json -Depth 12

Write-Host "Complete failed test run"
Invoke-ScavLifeRoute "/singleplayer/scavlife/debug/complete-run" @{
    profileId = $ProfileId
    survived = $false
    location = "woods"
    lootValue = 1000
    itemsExtracted = 0
    kills = 0
} | ConvertTo-Json -Depth 12

Write-Host "Dossier after failed run"
Invoke-ScavLifeRoute "/singleplayer/scavlife/dossier" @{ profileId = $ProfileId } | ConvertTo-Json -Depth 12

Write-Host "Reset clean"
Invoke-ScavLifeRoute "/singleplayer/scavlife/debug/reset" @{ profileId = $ProfileId } | ConvertTo-Json -Depth 12
