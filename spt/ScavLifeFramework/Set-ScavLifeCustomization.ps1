param(
    [switch] $AllowStateChanges,
    [string] $BaseUrl = "https://127.0.0.1:6969",
    [string] $ProfileId = "local-test",
    [string] $Nickname = "Local Runner",
    [string] $Archetype = "courier",
    [string] $HomeMap = "tarkovstreets",
    [string] $Temperament = "cautious",
    [string] $Voice = "quiet",
    [string] $OutfitPreset = "scrapper",
    [string] $PrimaryWeapon = "smg",
    [string] $Armor = "light",
    [string] $Backpack = "small-pack",
    [string] $Medical = "balanced",
    [string] $LootFocus = "hardware",
    [string[]] $Tags = @("local", "persistent", "transit-ready")
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

    $json = $Body | ConvertTo-Json -Depth 12
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

$body = @{
    profileId = $ProfileId
    nickname = $Nickname
    archetype = $Archetype
    homeMap = $HomeMap
    temperament = $Temperament
    voice = $Voice
    outfitPreset = $OutfitPreset
    tags = $Tags
    kitPreferences = @{
        primaryWeapon = $PrimaryWeapon
        armor = $Armor
        backpack = $Backpack
        medical = $Medical
        lootFocus = $LootFocus
    }
}

Write-Host "Apply custom scav identity"
Invoke-ScavLifeRoute "/singleplayer/scavlife/customization/apply" $body | ConvertTo-Json -Depth 12

Write-Host "Status"
Invoke-ScavLifeRoute "/singleplayer/scavlife/status" @{ profileId = $ProfileId } | ConvertTo-Json -Depth 12
