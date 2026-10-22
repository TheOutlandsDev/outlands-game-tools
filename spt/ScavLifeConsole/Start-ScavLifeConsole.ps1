param(
    [Parameter(Mandatory)][string] $GameRoot,
    [switch] $EnableMutations,
    [string] $ListenPrefix = "http://127.0.0.1:7777/",
    [string] $SptBaseUrl = "https://127.0.0.1:6969",
    [string] $ProfileId = "local-test",
    [switch] $NoBrowser
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot 'ConsoleSecurity.ps1')
$consoleOrigin = Get-LoopbackOrigin -Value $ListenPrefix -AllowedSchemes @('http')
$SptBaseUrl = Get-LoopbackOrigin -Value $SptBaseUrl
$ListenPrefix = "$consoleOrigin/"
$consoleAuthority = ([Uri]$consoleOrigin).Authority
$apiToken = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
if ($ProfileId -notmatch '^[A-Za-z0-9_-]{1,64}$') { throw 'ProfileId must contain 1-64 letters, digits, underscores, or hyphens.' }

if (-not ("System.IO.Compression.ZLibStream" -as [type])) {
    throw "Scav Life Console requires PowerShell 7+ because SPT uses zlib request/response bodies. Run this with pwsh."
}

$webRoot = Join-Path $PSScriptRoot "www"
if (-not (Test-Path -LiteralPath $webRoot -PathType Container)) {
    throw "Web root not found: $webRoot"
}

$workspaceRoot = (Resolve-Path -LiteralPath $GameRoot).Path
if (-not (Test-Path -LiteralPath $workspaceRoot -PathType Container)) { throw "GameRoot must be a directory." }

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

    if ($Bytes.Length -eq 0) {
        return ""
    }

    $inputStream = [System.IO.MemoryStream]::new($Bytes)
    $zlibStream = [System.IO.Compression.ZLibStream]::new($inputStream, [System.IO.Compression.CompressionMode]::Decompress)
    $reader = [System.IO.StreamReader]::new($zlibStream, [System.Text.Encoding]::UTF8)
    $text = $reader.ReadToEnd()
    $reader.Dispose()
    $inputStream.Dispose()
    return $text
}

function Read-RequestText {
    param([System.Net.HttpListenerRequest] $Request)

    if (-not $Request.HasEntityBody) {
        return ""
    }

    $reader = [System.IO.StreamReader]::new($Request.InputStream, $Request.ContentEncoding)
    try {
        $buffer = [char[]]::new(1048577)
        $count = $reader.ReadBlock($buffer, 0, $buffer.Length)
        if ($count -gt 1048576) { throw 'Request body exceeds 1 MiB.' }
        return [string]::new($buffer, 0, $count)
    }
    finally {
        $reader.Dispose()
    }
}

function Write-BytesResponse {
    param(
        [System.Net.HttpListenerResponse] $Response,
        [byte[]] $Bytes,
        [string] $ContentType,
        [int] $StatusCode = 200
    )

    $Response.StatusCode = $StatusCode
    $Response.ContentType = $ContentType
    $Response.ContentLength64 = $Bytes.Length
    $Response.Headers["Cache-Control"] = "no-store"
    $Response.Headers["X-Content-Type-Options"] = "nosniff"
    $Response.Headers["X-Frame-Options"] = "DENY"
    $Response.Headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'"
    $Response.OutputStream.Write($Bytes, 0, $Bytes.Length)
    $Response.OutputStream.Close()
}

function Write-JsonResponse {
    param(
        [System.Net.HttpListenerResponse] $Response,
        [object] $Data,
        [int] $StatusCode = 200
    )

    $json = $Data | ConvertTo-Json -Depth 32
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
    Write-BytesResponse -Response $Response -Bytes $bytes -ContentType "application/json; charset=utf-8" -StatusCode $StatusCode
}

function Get-ContentType {
    param([string] $Path)

    switch ([System.IO.Path]::GetExtension($Path).ToLowerInvariant()) {
        ".html" { return "text/html; charset=utf-8" }
        ".css" { return "text/css; charset=utf-8" }
        ".js" { return "application/javascript; charset=utf-8" }
        ".json" { return "application/json; charset=utf-8" }
        ".svg" { return "image/svg+xml" }
        default { return "application/octet-stream" }
    }
}

function Invoke-SptRoute {
    param(
        [string] $Path,
        [hashtable] $Body
    )

    $json = $Body | ConvertTo-Json -Depth 32
    $bodyBytes = ConvertTo-ZlibBytes $json

    $handler = [System.Net.Http.HttpClientHandler]::new()
    $handler.AllowAutoRedirect = $false
    $client = [System.Net.Http.HttpClient]::new($handler)
    try {
        $content = [System.Net.Http.ByteArrayContent]::new($bodyBytes)
        $content.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse("application/json")
        $response = $client.PostAsync("$SptBaseUrl$Path", $content).GetAwaiter().GetResult()
        $bytes = $response.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult()
        $text = ConvertFrom-ZlibBytes $bytes

        if (-not $response.IsSuccessStatusCode) {
            throw "SPT returned HTTP $([int]$response.StatusCode): $text"
        }

        if ([string]::IsNullOrWhiteSpace($text)) {
            return @{}
        }

        return $text | ConvertFrom-Json -AsHashtable
    }
    finally {
        $client.Dispose()
    }
}

function Read-JsonFileSafe {
    param([string] $Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }

    try {
        return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -AsHashtable
    }
    catch {
        return @{
            parseError = $_.Exception.Message
        }
    }
}

function Normalize-Key {
    param([string] $Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return ""
    }

    return [regex]::Replace($Value.ToLowerInvariant(), "[^a-z0-9]", "")
}

function Get-NumberOrNull {
    param($Value)

    if ($null -eq $Value -or $Value -eq "") {
        return $null
    }

    try {
        return [double]$Value
    }
    catch {
        return $null
    }
}

function Get-RoundedAverage {
    param([double[]] $Values)

    if ($null -eq $Values -or $Values.Count -eq 0) {
        return $null
    }

    return [math]::Round(($Values | Measure-Object -Average).Average, 2)
}

function Get-RoundedMinimum {
    param([double[]] $Values)

    if ($null -eq $Values -or $Values.Count -eq 0) {
        return $null
    }

    return [math]::Round(($Values | Measure-Object -Minimum).Minimum, 2)
}

function Get-RoundedMaximum {
    param([double[]] $Values)

    if ($null -eq $Values -or $Values.Count -eq 0) {
        return $null
    }

    return [math]::Round(($Values | Measure-Object -Maximum).Maximum, 2)
}

function Read-JsonLinesSafe {
    param(
        [string] $Path,
        [int] $Limit = 0
    )

    $events = New-Object System.Collections.Generic.List[object]
    $parseErrors = 0
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return @{
            events = @()
            parseErrors = 0
        }
    }

    foreach ($line in Get-Content -LiteralPath $Path) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        try {
            [void]$events.Add(($line | ConvertFrom-Json -AsHashtable))
        }
        catch {
            $parseErrors++
        }

        if ($Limit -gt 0 -and $events.Count -ge $Limit) {
            break
        }
    }

    return @{
        events = $events.ToArray()
        parseErrors = $parseErrors
    }
}

function Get-FileSummary {
    param([string] $Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }

    $file = Get-Item -LiteralPath $Path
    return @{
        name = $file.Name
        fullName = $file.FullName
        sizeBytes = $file.Length
        sizeKb = [math]::Round($file.Length / 1kb, 1)
        lastWriteTime = $file.LastWriteTime.ToString("s")
        lastWriteUnixTime = ([DateTimeOffset]$file.LastWriteTime.ToUniversalTime()).ToUnixTimeSeconds()
    }
}

function Get-DirectorySummary {
    param([string] $Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        return $null
    }

    $directory = Get-Item -LiteralPath $Path
    return @{
        name = $directory.Name
        fullName = $directory.FullName
        lastWriteTime = $directory.LastWriteTime.ToString("s")
        lastWriteUnixTime = ([DateTimeOffset]$directory.LastWriteTime.ToUniversalTime()).ToUnixTimeSeconds()
    }
}

function Get-ChildValue {
    param(
        $Object,
        [string] $Key
    )

    if ($null -eq $Object) {
        return $null
    }

    if ($Object -is [hashtable] -and $Object.ContainsKey($Key)) {
        return $Object[$Key]
    }

    if ($Object -is [hashtable]) {
        foreach ($entryKey in $Object.Keys) {
            if ([string]$entryKey -ieq $Key) {
                return $Object[$entryKey]
            }
        }
    }

    return $null
}

function Get-ArrayCount {
    param($Value)

    if ($null -eq $Value) {
        return 0
    }

    return @($Value).Count
}

function Get-CounterValue {
    param(
        $Counters,
        [string[]] $RequiredKeys
    )

    foreach ($counter in @($Counters)) {
        $keys = @(Get-ChildValue $counter "Key")
        if ($keys.Count -eq 0) {
            $keys = @(Get-ChildValue $counter "key")
        }

        $matches = $true
        foreach ($requiredKey in $RequiredKeys) {
            if (($keys | Where-Object { [string]$_ -ieq $requiredKey }).Count -eq 0) {
                $matches = $false
                break
            }
        }

        if ($matches) {
            $value = Get-ChildValue $counter "Value"
            if ($null -eq $value) {
                $value = Get-ChildValue $counter "value"
            }

            return Get-NumberOrNull $value
        }
    }

    return 0
}

function Get-KnownTraderMap {
    $traderRoot = Join-Path $workspaceRoot "SPT\SPT_Data\database\traders"
    $known = @{}
    foreach ($directory in @(Get-ChildItem -LiteralPath $traderRoot -Directory -ErrorAction SilentlyContinue)) {
        $basePath = Join-Path $directory.FullName "base.json"
        $base = Read-JsonFileSafe -Path $basePath
        $id = $directory.Name
        $name = $id
        if ($base) {
            $id = [string]$(if ($base.ContainsKey("_id")) { $base["_id"] } else { $directory.Name })
            $name = [string]$(if ($base.ContainsKey("nickname")) { $base["nickname"] } elseif ($base.ContainsKey("name")) { $base["name"] } else { $id })
        }

        $known[$id] = @{
            id = $id
            name = $name
            path = $directory.FullName
        }
    }

    return $known
}

function Get-ProcessSummary {
    $processes = @(Get-Process -ErrorAction SilentlyContinue)
    $names = @($processes | ForEach-Object { $_.ProcessName })

    return @{
        sptServer = @($processes | Where-Object { $_.ProcessName -match "^SPT\.Server$|SPT\.Server|Aki.Server" } | Select-Object -First 1 | ForEach-Object { @{ name = $_.ProcessName; id = $_.Id } })
        game = @($processes | Where-Object { $_.ProcessName -match "EscapeFromTarkov" } | Select-Object -First 1 | ForEach-Object { @{ name = $_.ProcessName; id = $_.Id } })
        launcher = @($processes | Where-Object { $_.ProcessName -match "Launcher|FikaSync|Greed" } | Select-Object -First 1 | ForEach-Object { @{ name = $_.ProcessName; id = $_.Id } })
        sptServerRunning = @($names | Where-Object { $_ -match "^SPT\.Server$|SPT\.Server|Aki.Server" }).Count -gt 0
        gameRunning = @($names | Where-Object { $_ -match "EscapeFromTarkov" }).Count -gt 0
        launcherRunning = @($names | Where-Object { $_ -match "Launcher|FikaSync|Greed" }).Count -gt 0
    }
}

function Get-ModStackSummary {
    $serverModRoot = Join-Path $workspaceRoot "SPT\user\mods"
    $clientPluginRoot = Join-Path $workspaceRoot "BepInEx\plugins"
    $disabledRoot = Join-Path $workspaceRoot "_codex_disabled"
    $customToolsRoot = Join-Path $workspaceRoot "custom-tools"
    $serverMods = @(Get-ChildItem -LiteralPath $serverModRoot -Directory -ErrorAction SilentlyContinue | Sort-Object Name)
    $clientPlugins = @(Get-ChildItem -LiteralPath $clientPluginRoot -Recurse -File -Filter "*.dll" -ErrorAction SilentlyContinue | Sort-Object FullName)
    $disabledArchives = @(Get-ChildItem -LiteralPath $disabledRoot -Directory -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)
    $customTools = @(Get-ChildItem -LiteralPath $customToolsRoot -Directory -ErrorAction SilentlyContinue | Sort-Object Name)

    $serverNames = @($serverMods | ForEach-Object { $_.Name })
    $pluginNames = @($clientPlugins | ForEach-Object { $_.FullName.Substring($clientPluginRoot.Length).TrimStart("\") })
    $serverModDetails = @($serverMods | ForEach-Object {
        @{
            name = $_.Name
            path = $_.FullName
            lastWriteTime = $_.LastWriteTime.ToString("s")
            hasDll = @(Get-ChildItem -LiteralPath $_.FullName -File -Filter "*.dll" -ErrorAction SilentlyContinue).Count -gt 0
            hasPackageJson = Test-Path -LiteralPath (Join-Path $_.FullName "package.json") -PathType Leaf
            hasConfig = (Test-Path -LiteralPath (Join-Path $_.FullName "config.json") -PathType Leaf) -or (Test-Path -LiteralPath (Join-Path $_.FullName "config") -PathType Container)
        }
    })
    $clientPluginDetails = @($clientPlugins | ForEach-Object {
        @{
            name = $_.Name
            relativePath = $_.FullName.Substring($clientPluginRoot.Length).TrimStart("\")
            folder = Split-Path ($_.FullName.Substring($clientPluginRoot.Length).TrimStart("\")) -Parent
            sizeKb = [math]::Round($_.Length / 1kb, 1)
            lastWriteTime = $_.LastWriteTime.ToString("s")
        }
    })
    $customToolDetails = @($customTools | ForEach-Object {
        @{
            name = $_.Name
            path = $_.FullName
            buildScripts = @((Get-ChildItem -LiteralPath $_.FullName -File -Filter "Build-*.ps1" -ErrorAction SilentlyContinue).Name)
            readme = Test-Path -LiteralPath (Join-Path $_.FullName "README.md") -PathType Leaf
            sourceFiles = @(Get-ChildItem -LiteralPath $_.FullName -Recurse -File -Include "*.cs", "*.ps1", "*.js", "*.html", "*.css" -ErrorAction SilentlyContinue).Count
        }
    })
    $categories = @(
        @{
            name = "AI and bots"
            count = @($serverNames + $pluginNames | Where-Object { $_ -match "SAIN|BigBrain|Waypoints|MoreBots|LootingBots|Scavs4All|FikaDynamicAI|TwitchPlayers" }).Count
        }
        @{
            name = "Graphics and feel"
            count = @($serverNames + $pluginNames | Where-Object { $_ -match "Graphics|Shaders|Thermal|Shadow|Ambience|Bodycam|Movement|Stamina" }).Count
        }
        @{
            name = "Content and items"
            count = @($serverNames + $pluginNames | Where-Object { $_ -match "WTT|Backport|Armory|FPV|RUAFComeHome|UNTAR|Backpacks|Foldables|Energy|Voice" }).Count
        }
        @{
            name = "Codex systems"
            count = @($serverNames + $pluginNames | Where-Object { $_ -match "Codex|QuakeBrain|ScavLife|OpenScavTransits|Diagnostics" }).Count
        }
    )

    $systems = @(
        @{ name = "Fika server"; installed = $serverNames -contains "fika-server"; side = "server" }
        @{ name = "Fika client"; installed = ($pluginNames -match "Fika\\Fika.Core.dll").Count -gt 0; side = "client" }
        @{ name = "SAIN"; installed = ($pluginNames -match "SAIN\\SAIN.dll").Count -gt 0; side = "client" }
        @{ name = "BigBrain"; installed = ($pluginNames -match "DrakiaXYZ-BigBrain.dll").Count -gt 0; side = "client" }
        @{ name = "Waypoints"; installed = ($pluginNames -match "DrakiaXYZ-Waypoints.dll").Count -gt 0; side = "client" }
        @{ name = "MoreBots"; installed = ($serverNames -contains "MoreBotsServer") -or (($pluginNames -match "MoreBots").Count -gt 0); side = "both" }
        @{ name = "Scav Life"; installed = $serverNames -contains "000-ScavLifeFramework"; side = "server" }
        @{ name = "Open Scav Transits"; installed = $serverNames -contains "zzz-CodexOpenScavTransits"; side = "server" }
        @{ name = "QuakeBrain telemetry"; installed = ($pluginNames -match "QuakeBrain\\QuakeBrain.Telemetry.dll").Count -gt 0; side = "client" }
        @{ name = "Codex Diagnostics"; installed = ($pluginNames -match "CodexDiagnostics\\Codex.Diagnostics.Client.dll").Count -gt 0; side = "client" }
    )

    return @{
        serverModCount = $serverMods.Count
        clientPluginCount = $clientPlugins.Count
        disabledArchiveCount = $disabledArchives.Count
        systems = $systems
        categories = $categories
        serverModDetails = $serverModDetails
        clientPluginDetails = $clientPluginDetails
        disabledArchives = @($disabledArchives | ForEach-Object { Get-DirectorySummary -Path $_.FullName })
        customTools = $customToolDetails
        serverMods = @($serverNames | Select-Object -First 80)
        clientPlugins = @($pluginNames | Select-Object -First 80)
    }
}

function Get-ScavLifeLocalSummary {
    param([string] $ProfileId)

    $statePath = Join-Path $workspaceRoot "SPT\user\mods\000-ScavLifeFramework\data\scav_life_state.json"
    $configPath = Join-Path $workspaceRoot "SPT\user\mods\000-ScavLifeFramework\config\config.json"
    $state = Read-JsonFileSafe -Path $statePath
    $config = Read-JsonFileSafe -Path $configPath
    $profile = $null

    if ($state -and $state.ContainsKey("profiles")) {
        $profiles = $state["profiles"]
        if ($profiles.ContainsKey($ProfileId)) {
            $profile = $profiles[$ProfileId]
        }
        elseif ($profiles.Count -gt 0) {
            $firstProfileKey = $profiles.Keys | Select-Object -First 1
            $profile = $profiles[$firstProfileKey]
        }
    }

    $stats = if ($profile) { $profile["stats"] } else { $null }
    $dossier = if ($profile) { $profile["dossier"] } else { $null }
    $scav = if ($profile) { $profile["activeScav"] } else { $null }

    return @{
        installed = Test-Path -LiteralPath (Join-Path $workspaceRoot "SPT\user\mods\000-ScavLifeFramework\Codex.ScavLifeFramework.dll")
        stateFile = Get-FileSummary -Path $statePath
        configFile = Get-FileSummary -Path $configPath
        schemaVersion = if ($state) { $state["schemaVersion"] } else { $null }
        profileId = if ($profile) { $profile["profileId"] } else { $ProfileId }
        nickname = if ($scav) { $scav["nickname"] } else { $null }
        alive = if ($scav) { $scav["alive"] } else { $null }
        level = if ($scav) { $scav["level"] } else { $null }
        experience = if ($scav) { $scav["experience"] } else { $null }
        runsStarted = if ($stats) { $stats["runsStarted"] } else { 0 }
        runsSurvived = if ($stats) { $stats["runsSurvived"] } else { 0 }
        runsFailed = if ($stats) { $stats["runsFailed"] } else { 0 }
        kills = if ($stats) { $stats["kills"] } else { 0 }
        itemsExtracted = if ($stats) { $stats["itemsExtracted"] } else { 0 }
        totalLootValue = if ($stats) { $stats["totalLootValue"] } else { 0 }
        lastOutcome = if ($dossier) { $dossier["lastOutcome"] } else { "none" }
        lastCaptureSource = if ($dossier -and $dossier.ContainsKey("lastCaptureSource")) { $dossier["lastCaptureSource"] } else { "none" }
        lastRaidLocation = if ($dossier) { $dossier["lastRaidLocation"] } else { "unknown" }
        survivalStreak = if ($dossier) { $dossier["survivalStreak"] } else { 0 }
        trust = if ($dossier) { $dossier["trust"] } else { 0 }
        stress = if ($dossier) { $dossier["stress"] } else { 0 }
        fatigue = if ($dossier) { $dossier["fatigue"] } else { 0 }
        liveSyncEnabled = if ($config) { [bool]$config["customization"]["syncToLivePlayerScav"] } else { $false }
    }
}

function Get-ProfileCharacter {
    param(
        $Profile,
        [string] $Side
    )

    $characters = Get-ChildValue $Profile "characters"
    if ($characters) {
        $character = Get-ChildValue $characters $Side
        if ($character) {
            return $character
        }
    }

    return Get-ChildValue $Profile $Side
}

function Get-CharacterCounterSummary {
    param($Character)

    $stats = Get-ChildValue $Character "Stats"
    $eft = Get-ChildValue $stats "Eft"
    $overall = Get-ChildValue $eft "OverallCounters"
    $counters = Get-ChildValue $overall "Items"

    return @{
        sessions = Get-CounterValue -Counters $counters -RequiredKeys @("Sessions")
        survived = Get-CounterValue -Counters $counters -RequiredKeys @("ExitStatus", "Survived")
        killed = Get-CounterValue -Counters $counters -RequiredKeys @("ExitStatus", "Killed")
        left = Get-CounterValue -Counters $counters -RequiredKeys @("ExitStatus", "Left")
        runner = Get-CounterValue -Counters $counters -RequiredKeys @("ExitStatus", "Runner")
        kills = Get-CounterValue -Counters $counters -RequiredKeys @("Kills")
        deaths = Get-CounterValue -Counters $counters -RequiredKeys @("Deaths")
        lifetimeSeconds = Get-CounterValue -Counters $counters -RequiredKeys @("LifeTime")
    }
}

function Get-ProfileHealthSummary {
    param([string] $ProfileId)

    $profilePath = Join-Path $workspaceRoot "SPT\user\profiles\$ProfileId.json"
    $profile = Read-JsonFileSafe -Path $profilePath
    $knownTraders = Get-KnownTraderMap
    $coreConfigPath = Join-Path $workspaceRoot "SPT\SPT_Data\configs\core.json"
    $coreConfig = Read-JsonFileSafe -Path $coreConfigPath
    $issues = New-Object System.Collections.Generic.List[object]

    if (-not $profile) {
        [void]$issues.Add(@{
            severity = "error"
            title = "Profile file not found"
            detail = "No profile JSON exists for $ProfileId."
        })

        return @{
            profileId = $ProfileId
            profileFile = $null
            issues = $issues.ToArray()
            issueCount = $issues.Count
        }
    }

    $pmc = Get-ProfileCharacter -Profile $profile -Side "pmc"
    $scav = Get-ProfileCharacter -Profile $profile -Side "scav"
    $pmcInfo = Get-ChildValue $pmc "Info"
    $scavInfo = Get-ChildValue $scav "Info"
    $pmcTraders = Get-ChildValue $pmc "TradersInfo"
    $dialogues = Get-ChildValue $profile "dialogues"
    $invalidTraderIds = @()
    $knownTraderIds = @($knownTraders.Keys)

    foreach ($traderId in @($pmcTraders.Keys)) {
        if (($knownTraderIds | Where-Object { $_ -ieq $traderId }).Count -eq 0) {
            $invalidTraderIds += [string]$traderId
        }
    }

    $invalidDialogues = @()
    if ($dialogues) {
        foreach ($dialogueId in @($dialogues.Keys)) {
            if ($dialogueId -match "^[a-f0-9]{24}$" -and ($knownTraderIds | Where-Object { $_ -ieq $dialogueId }).Count -eq 0) {
                $invalidDialogues += [string]$dialogueId
            }
        }
    }

    if ($invalidTraderIds.Count -gt 0) {
        [void]$issues.Add(@{
            severity = "error"
            title = "Invalid trader references in profile"
            detail = "Unknown trader ids: $($invalidTraderIds -join ', ')"
        })
    }

    $fixes = if ($coreConfig) { Get-ChildValue $coreConfig "fixes" } else { $null }
    $removeModItems = [bool](Get-ChildValue $fixes "removeModItemsFromProfile")
    $removeInvalidTraders = [bool](Get-ChildValue $fixes "removeInvalidTradersFromProfile")
    if ($invalidTraderIds.Count -gt 0 -and -not $removeInvalidTraders) {
        [void]$issues.Add(@{
            severity = "warn"
            title = "Profile fixer is not removing invalid traders"
            detail = "SPT core config has removeInvalidTradersFromProfile=false."
        })
    }

    if ($invalidDialogues.Count -gt 0 -and -not $removeModItems) {
        $sampleInvalidDialogues = ($invalidDialogues | Select-Object -First 5) -join ', '
        [void]$issues.Add(@{
            severity = "warn"
            title = "Profile fixer is not removing mod dialogue/items"
            detail = "Potential stale dialogue ids: $sampleInvalidDialogues"
        })
    }

    $scavLife = Get-ScavLifeLocalSummary -ProfileId $ProfileId
    if ($scavLife.schemaVersion -and [int]$scavLife.schemaVersion -lt 4) {
        [void]$issues.Add(@{
            severity = "info"
            title = "Scav Life state will migrate on next server start"
            detail = "State schema is $($scavLife.schemaVersion); the installed DLL expects schema 4."
        })
    }

    $pmcInventory = Get-ChildValue (Get-ChildValue $pmc "Inventory") "items"
    $scavInventory = Get-ChildValue (Get-ChildValue $scav "Inventory") "items"
    $pmcCounters = Get-CharacterCounterSummary -Character $pmc
    $scavCounters = Get-CharacterCounterSummary -Character $scav

    return @{
        profileId = $ProfileId
        profileFile = Get-FileSummary -Path $profilePath
        pmc = @{
            nickname = Get-ChildValue $pmcInfo "Nickname"
            side = Get-ChildValue $pmcInfo "Side"
            level = Get-ChildValue $pmcInfo "Level"
            experience = Get-ChildValue $pmcInfo "Experience"
            inventoryItems = Get-ArrayCount $pmcInventory
            counters = $pmcCounters
        }
        scav = @{
            nickname = Get-ChildValue $scavInfo "Nickname"
            side = Get-ChildValue $scavInfo "Side"
            level = Get-ChildValue $scavInfo "Level"
            experience = Get-ChildValue $scavInfo "Experience"
            lockTime = Get-ChildValue $scavInfo "SavageLockTime"
            inventoryItems = Get-ArrayCount $scavInventory
            counters = $scavCounters
        }
        knownTraderCount = $knownTraders.Count
        profileTraderCount = if ($pmcTraders) { $pmcTraders.Keys.Count } else { 0 }
        invalidTraderIds = $invalidTraderIds
        invalidDialogueIds = $invalidDialogues
        coreFixes = @{
            removeModItemsFromProfile = $removeModItems
            removeInvalidTradersFromProfile = $removeInvalidTraders
            fixProfileBreakingInventoryItemIssues = [bool](Get-ChildValue $fixes "fixProfileBreakingInventoryItemIssues")
        }
        issues = $issues.ToArray()
        issueCount = $issues.Count
        worstSeverity = if (($issues | Where-Object { $_.severity -eq "error" }).Count -gt 0) { "error" } elseif (($issues | Where-Object { $_.severity -eq "warn" }).Count -gt 0) { "warn" } elseif ($issues.Count -gt 0) { "info" } else { "ok" }
    }
}

function Get-TraderAvailabilitySummary {
    $configPath = Join-Path $workspaceRoot "SPT\user\mods\zzz-CodexOpenScavTransits\config\config.json"
    $statePath = Join-Path $workspaceRoot "SPT\user\mods\zzz-CodexOpenScavTransits\data\trader_availability_state.json"
    $config = Read-JsonFileSafe -Path $configPath
    $state = Read-JsonFileSafe -Path $statePath
    $traderNames = @{
        "579dc571d53a0658a154fbec" = "Fence"
        "54cb50c76803fa8b248b4571" = "Prapor"
        "54cb57776803fa99248b456e" = "Therapist"
        "58330581ace78e27b8b10cee" = "Skier"
        "5935c25fb3acc3127c3d8cd9" = "Peacekeeper"
        "5a7c2eca46aef81a7ca2145d" = "Mechanic"
        "5ac3b934156ae10c4430e83c" = "Ragman"
        "5c0647fdd443bc2504c2d371" = "Jaeger"
        "6617beeaa9cfa777ca915b7c" = "Ref"
    }

    if (-not $config -or -not $config.ContainsKey("TraderAvailability")) {
        return @{
            installed = Test-Path -LiteralPath (Join-Path $workspaceRoot "SPT\user\mods\zzz-CodexOpenScavTransits\Codex.OpenScavTransits.dll")
            enabled = $false
        }
    }

    $availability = $config["TraderAvailability"]
    $currentLocation = if ($state -and $state.ContainsKey("CurrentLocation")) { [string]$state["CurrentLocation"] } else { [string]$availability["DefaultLocation"] }
    $normalizedLocation = Normalize-Key $currentLocation
    $extraIds = @()
    $rules = $availability["MapTraderRules"]
    if ($rules) {
        foreach ($key in $rules.Keys) {
            if ((Normalize-Key $key) -eq $normalizedLocation) {
                $extraIds = @($rules[$key])
                break
            }
        }
    }

    if ($extraIds.Count -eq 0) {
        $extraIds = @($availability["RotationPool"] | Select-Object -First ([int]$availability["ExtraTraderCount"]))
    }

    $fenceId = [string]$availability["FenceTraderId"]
    $availableIds = @($fenceId) + @($extraIds | Select-Object -First ([int]$availability["ExtraTraderCount"]))
    $available = @($availableIds | ForEach-Object {
        @{
            id = $_
            name = if ($traderNames.ContainsKey($_)) { $traderNames[$_] } else { $_ }
        }
    })

    return @{
        installed = Test-Path -LiteralPath (Join-Path $workspaceRoot "SPT\user\mods\zzz-CodexOpenScavTransits\Codex.OpenScavTransits.dll")
        enabled = [bool]$availability["Enabled"]
        currentLocation = $currentLocation
        raidCounter = if ($state) { $state["RaidCounter"] } else { 0 }
        updatedUtc = if ($state) { $state["UpdatedUtc"] } else { $null }
        lastUpdateSource = if ($state) { $state["LastUpdateSource"] } else { "default" }
        rotationMode = $availability["RotationMode"]
        extraTraderCount = $availability["ExtraTraderCount"]
        availableTraders = $available
        scavAccessMaps = @($config["ScavAccessMaps"])
        transitsEnabled = [bool]$config["EnableExistingTransits"]
    }
}

function Get-QuakeBrainSummary {
    $directory = Join-Path $workspaceRoot "Logs\QuakeBrainTelemetry"
    $recentFiles = @(Get-ChildItem -LiteralPath $directory -File -Filter "raid-*.jsonl" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 5)
    $latest = $recentFiles | Select-Object -First 1

    if ($null -eq $latest) {
        return @{
            installed = Test-Path -LiteralPath (Join-Path $workspaceRoot "BepInEx\plugins\QuakeBrain\QuakeBrain.Telemetry.dll")
            hasData = $false
            directory = $directory
            recentFiles = @()
        }
    }

    $read = Read-JsonLinesSafe -Path $latest.FullName
    $events = @($read.events)
    $eventCounts = @{}
    $snapshotCount = 0
    $botTotal = 0
    $maxBots = 0
    $trackedTotal = 0
    $trackedSamples = 0
    $maxTracked = 0
    $map = ""
    $raidSeconds = 0
    $droppedLines = 0

    foreach ($event in $events) {
        $type = [string]$event["type"]
        if (-not $eventCounts.ContainsKey($type)) {
            $eventCounts[$type] = 0
        }
        $eventCounts[$type]++

        $payload = $event["payload"]
        if ($payload -and $payload.ContainsKey("map")) {
            $map = [string]$payload["map"]
        }
        if ($payload -and $payload.ContainsKey("raid_seconds")) {
            $raidSeconds = [double]$payload["raid_seconds"]
        }

        if ($type -eq "snapshot") {
            $snapshotCount++
            $botCount = [int](Get-NumberOrNull $payload["bot_count"])
            $botTotal += $botCount
            $maxBots = [math]::Max($maxBots, $botCount)

            if ($payload.ContainsKey("tracking") -and $payload["tracking"]) {
                $tracked = [int](Get-NumberOrNull $payload["tracking"]["active_count"])
                $trackedSamples++
                $trackedTotal += $tracked
                $maxTracked = [math]::Max($maxTracked, $tracked)
            }
        }

        if ($type -eq "raid_end" -and $payload -and $payload.ContainsKey("dropped_lines")) {
            $droppedLines = [int](Get-NumberOrNull $payload["dropped_lines"])
        }
    }

    return @{
        installed = $true
        hasData = $true
        file = Get-FileSummary -Path $latest.FullName
        map = $map
        raidSeconds = [math]::Round($raidSeconds, 1)
        events = $events.Count
        snapshots = $snapshotCount
        avgBots = if ($snapshotCount -gt 0) { [math]::Round($botTotal / $snapshotCount, 2) } else { 0 }
        maxBots = $maxBots
        avgTrackedActive = if ($trackedSamples -gt 0) { [math]::Round($trackedTotal / $trackedSamples, 2) } else { 0 }
        maxTrackedActive = $maxTracked
        trackingAssignments = if ($eventCounts.ContainsKey("tracking_assigned")) { $eventCounts["tracking_assigned"] } else { 0 }
        droppedLines = $droppedLines
        parseErrors = $read.parseErrors
        recentFiles = @($recentFiles | ForEach-Object { Get-FileSummary -Path $_.FullName })
        topEventTypes = @($eventCounts.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 10 | ForEach-Object { @{ type = $_.Key; count = $_.Value } })
        eventCounts = $eventCounts
    }
}

function Get-DiagnosticsSummary {
    $directory = Join-Path $workspaceRoot "Logs\CodexDiagnostics"
    $latest = Get-ChildItem -LiteralPath $directory -File -Filter "client-*.jsonl" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if ($null -eq $latest) {
        return @{
            installed = Test-Path -LiteralPath (Join-Path $workspaceRoot "BepInEx\plugins\CodexDiagnostics\Codex.Diagnostics.Client.dll")
            hasData = $false
            directory = $directory
        }
    }

    $read = Read-JsonLinesSafe -Path $latest.FullName
    $events = @($read.events)
    $fpsValues = New-Object System.Collections.Generic.List[double]
    $maxFrameValues = New-Object System.Collections.Generic.List[double]
    $p95FrameValues = New-Object System.Collections.Generic.List[double]
    $hitches = 0
    $hitchEvents = 0
    $unityWarnings = 0
    $unityErrors = 0
    $maxAliveBots = 0
    $locations = New-Object System.Collections.Generic.HashSet[string]
    $eventCounts = @{}
    $topHitches = New-Object System.Collections.Generic.List[object]
    $unityMessageGroups = @{}
    $frameBuckets = @{
        le16 = 0
        le33 = 0
        le50 = 0
        le100 = 0
        gt100 = 0
    }

    foreach ($event in $events) {
        $type = [string]$event["type"]
        if (-not $eventCounts.ContainsKey($type)) {
            $eventCounts[$type] = 0
        }
        $eventCounts[$type]++

        $payload = $event["payload"]
        if ($type -eq "performance_sample" -and $payload) {
            $fps = Get-NumberOrNull $payload["fps"]
            if ($null -ne $fps) { [void]$fpsValues.Add($fps) }
            $maxFrame = Get-NumberOrNull $payload["max_frame_ms"]
            if ($null -ne $maxFrame) { [void]$maxFrameValues.Add($maxFrame) }
            $p95 = Get-NumberOrNull $payload["p95_frame_ms"]
            if ($null -ne $p95) { [void]$p95FrameValues.Add($p95) }
            $hitchCount = Get-NumberOrNull $payload["hitch_count"]
            if ($null -ne $hitchCount) { $hitches += [int]$hitchCount }
            $buckets = Get-ChildValue $payload "frame_buckets"
            if ($buckets) {
                $frameBuckets.le16 += [int](Get-NumberOrNull (Get-ChildValue $buckets "le_16_7_ms"))
                $frameBuckets.le33 += [int](Get-NumberOrNull (Get-ChildValue $buckets "le_33_3_ms"))
                $frameBuckets.le50 += [int](Get-NumberOrNull (Get-ChildValue $buckets "le_50_ms"))
                $frameBuckets.le100 += [int](Get-NumberOrNull (Get-ChildValue $buckets "le_100_ms"))
                $frameBuckets.gt100 += [int](Get-NumberOrNull (Get-ChildValue $buckets "gt_100_ms"))
            }
        }
        elseif ($type -eq "hitch") {
            $hitchEvents++
            [void]$topHitches.Add(@{
                utc = Get-ChildValue $event "utc"
                frameMs = Get-NumberOrNull (Get-ChildValue $payload "frame_ms")
                scene = Get-ChildValue $payload "scene"
                location = Get-ChildValue (Get-ChildValue $payload "raid") "location"
                aliveBots = Get-ChildValue (Get-ChildValue $payload "raid") "alive_bot_owners"
                cpuPercent = Get-ChildValue (Get-ChildValue $payload "process") "cpu_percent"
                allocatedMb = Get-ChildValue (Get-ChildValue $payload "memory") "allocated_mb"
            })
        }
        elseif ($type -eq "unity_log" -and $payload) {
            $level = [string]$payload["level"]
            if ($level -match "Warning") { $unityWarnings++ }
            if ($level -match "Error|Exception|Assert") { $unityErrors++ }
            $message = [string](Get-ChildValue $payload "message")
            $key = "$level`: $message"
            if (-not $unityMessageGroups.ContainsKey($key)) {
                $unityMessageGroups[$key] = @{
                    count = 0
                    level = $level
                    message = $message
                }
            }
            $unityMessageGroups[$key].count++
        }
        elseif ($type -eq "raid_sample" -and $payload -and $payload["in_raid"] -eq $true) {
            $aliveBots = Get-NumberOrNull $payload["alive_bot_owners"]
            if ($null -ne $aliveBots) { $maxAliveBots = [math]::Max($maxAliveBots, [int]$aliveBots) }
            if (-not [string]::IsNullOrWhiteSpace([string]$payload["location"])) {
                [void]$locations.Add([string]$payload["location"])
            }
        }
    }

    return @{
        installed = $true
        hasData = $true
        file = Get-FileSummary -Path $latest.FullName
        events = $events.Count
        parseErrors = $read.parseErrors
        avgFps = Get-RoundedAverage -Values $fpsValues.ToArray()
        minFps = Get-RoundedMinimum -Values $fpsValues.ToArray()
        worstFrameMs = Get-RoundedMaximum -Values $maxFrameValues.ToArray()
        worstP95FrameMs = Get-RoundedMaximum -Values $p95FrameValues.ToArray()
        sampleHitches = $hitches
        hitchEvents = $hitchEvents
        unityWarnings = $unityWarnings
        unityErrors = $unityErrors
        maxAliveBotOwners = $maxAliveBots
        locations = @($locations)
        frameBuckets = $frameBuckets
        topHitches = @($topHitches | Sort-Object { [double]($_["frameMs"] ?? 0) } -Descending | Select-Object -First 10)
        topUnityMessages = @($unityMessageGroups.Values | Sort-Object { [int]$_["count"] } -Descending | Select-Object -First 10)
        eventCounts = $eventCounts
    }
}

function Get-SptLogSummary {
    $directory = Join-Path $workspaceRoot "SPT\user\logs\spt"
    $latest = Get-ChildItem -LiteralPath $directory -File -Filter "*.log" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if ($null -eq $latest) {
        return @{
            hasData = $false
            directory = $directory
        }
    }

    $tail = @(Get-Content -LiteralPath $latest.FullName -Tail 1200)
    $warnings = @($tail | Where-Object { $_ -match "\bwarn(ing)?\b" })
    $errors = @($tail | Where-Object { $_ -match "\berror\b|exception|failed" })
    $signals = @($tail | Where-Object { $_ -match "\bwarn(ing)?\b|\berror\b|exception|failed|Scav Life|Codex|Fika|ProfileFixer" } | Select-Object -Last 12)
    $routeCounts = @{}
    foreach ($line in $tail) {
        if ($line -match "\[(Client|WebSocket) Request\]\s+([^\s]+)") {
            $route = $Matches[2]
            if (-not $routeCounts.ContainsKey($route)) {
                $routeCounts[$route] = 0
            }
            $routeCounts[$route]++
        }
    }

    return @{
        hasData = $true
        file = Get-FileSummary -Path $latest.FullName
        recentWarningCount = $warnings.Count
        recentErrorCount = $errors.Count
        recentSignals = $signals
        recentErrors = @($errors | Select-Object -Last 10)
        topRoutes = @($routeCounts.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 12 | ForEach-Object { @{ route = $_.Key; count = $_.Value } })
    }
}

function Get-DashboardIssues {
    param(
        $ProfileHealth,
        $ScavLife,
        $Diagnostics,
        $QuakeBrain,
        $SptLog,
        $Processes
    )

    $issues = New-Object System.Collections.Generic.List[object]

    foreach ($issue in @($ProfileHealth.issues)) {
        [void]$issues.Add(@{
            severity = $issue.severity
            source = "Profile"
            title = $issue.title
            detail = $issue.detail
        })
    }

    if ($ScavLife.liveSyncEnabled -eq $true) {
        [void]$issues.Add(@{
            severity = "warn"
            source = "Scav Life"
            title = "Live scav sync is enabled"
            detail = "This build is meant to observe scav results after raid, not mutate the generated scav before spawn."
        })
    }

    if ($SptLog.recentErrorCount -gt 0) {
        [void]$issues.Add(@{
            severity = "error"
            source = "SPT Log"
            title = "$($SptLog.recentErrorCount) recent server error signals"
            detail = "Open the Logs tab for the latest matching lines."
        })
    }

    if ($Diagnostics.hasData -eq $true) {
        if ($Diagnostics.unityErrors -gt 0) {
            [void]$issues.Add(@{
                severity = "warn"
                source = "Diagnostics"
                title = "$($Diagnostics.unityErrors) Unity error/exception messages"
                detail = "Review the Performance tab for grouped Unity messages."
            })
        }

        if ($Diagnostics.sampleHitches -gt 50 -or $Diagnostics.worstFrameMs -gt 250) {
            [void]$issues.Add(@{
                severity = "warn"
                source = "Diagnostics"
                title = "Frame hitches detected"
                detail = "Worst captured frame: $($Diagnostics.worstFrameMs) ms; sample hitches: $($Diagnostics.sampleHitches)."
            })
        }
    }

    if ($QuakeBrain.installed -eq $true -and $QuakeBrain.hasData -ne $true) {
        [void]$issues.Add(@{
            severity = "info"
            source = "QuakeBrain"
            title = "No telemetry raid files yet"
            detail = "Telemetry will appear after a raid with the client plugin loaded."
        })
    }

    if ($Processes.sptServerRunning -ne $true) {
        [void]$issues.Add(@{
            severity = "info"
            source = "Runtime"
            title = "SPT server is not running"
            detail = "Local dashboard data is still available; live Scav Life routes will reconnect after SPT starts."
        })
    }

    return @{
        items = $issues.ToArray()
        count = $issues.Count
        errorCount = @($issues | Where-Object { $_.severity -eq "error" }).Count
        warningCount = @($issues | Where-Object { $_.severity -eq "warn" }).Count
        infoCount = @($issues | Where-Object { $_.severity -eq "info" }).Count
        worstSeverity = if (($issues | Where-Object { $_.severity -eq "error" }).Count -gt 0) { "error" } elseif (($issues | Where-Object { $_.severity -eq "warn" }).Count -gt 0) { "warn" } elseif ($issues.Count -gt 0) { "info" } else { "ok" }
    }
}

function Get-DashboardOverview {
    param([string] $RequestedProfileId)

    $resolvedProfileId = if ([string]::IsNullOrWhiteSpace($RequestedProfileId)) { $ProfileId } else { $RequestedProfileId }
    if ($resolvedProfileId -notmatch '^[A-Za-z0-9_-]{1,64}$') { throw 'Invalid profile ID.' }
    $processes = Get-ProcessSummary
    $modStack = Get-ModStackSummary
    $scavLife = Get-ScavLifeLocalSummary -ProfileId $resolvedProfileId
    $profileHealth = Get-ProfileHealthSummary -ProfileId $resolvedProfileId
    $traderAvailability = Get-TraderAvailabilitySummary
    $quakeBrain = Get-QuakeBrainSummary
    $diagnostics = Get-DiagnosticsSummary
    $sptLog = Get-SptLogSummary
    $issues = Get-DashboardIssues -ProfileHealth $profileHealth -ScavLife $scavLife -Diagnostics $diagnostics -QuakeBrain $quakeBrain -SptLog $sptLog -Processes $processes

    return @{
        ok = $true
        generatedAtUnixTime = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        workspaceRoot = $workspaceRoot
        profileId = $resolvedProfileId
        processes = $processes
        modStack = $modStack
        scavLife = $scavLife
        profileHealth = $profileHealth
        traderAvailability = $traderAvailability
        quakeBrain = $quakeBrain
        diagnostics = $diagnostics
        sptLog = $sptLog
        issues = $issues
    }
}

$routeMap = @{
    "/api/scavlife/status" = "/singleplayer/scavlife/status"
    "/api/scavlife/dossier" = "/singleplayer/scavlife/dossier"
    "/api/scavlife/raid-plan" = "/singleplayer/scavlife/raid-plan"
    "/api/scavlife/stash/status" = "/singleplayer/scavlife/stash/status"
    "/api/scavlife/stash/decision" = "/singleplayer/scavlife/stash/decision"
    "/api/scavlife/customization/options" = "/singleplayer/scavlife/customization/options"
    "/api/scavlife/customization/apply" = "/singleplayer/scavlife/customization/apply"
    "/api/scavlife/customization/randomize" = "/singleplayer/scavlife/customization/randomize"
    "/api/scavlife/debug/complete-run" = "/singleplayer/scavlife/debug/complete-run"
    "/api/scavlife/debug/reset" = "/singleplayer/scavlife/debug/reset"
    "/api/scavlife/debug/seed" = "/singleplayer/scavlife/debug/seed"
}

$mutationRoutes = @(
    '/api/scavlife/stash/decision', '/api/scavlife/customization/apply',
    '/api/scavlife/customization/randomize', '/api/scavlife/debug/complete-run',
    '/api/scavlife/debug/reset', '/api/scavlife/debug/seed'
)

$listener = [System.Net.HttpListener]::new()
$listener.Prefixes.Add($ListenPrefix)
$listener.Start()

Write-Host "SPT Build Dashboard listening at $ListenPrefix"
Write-Host "Proxying Scav Life routes to $SptBaseUrl"
Write-Host "ProfileId default: $ProfileId"
Write-Host "Press Ctrl+C to stop."

if (-not $NoBrowser) {
    Start-Process $ListenPrefix
}

try {
    while ($listener.IsListening) {
        $context = $listener.GetContext()
        $request = $context.Request
        $response = $context.Response

        try {
            $path = $request.Url.AbsolutePath

            $policy = @{
                Method = $request.HttpMethod; HostHeader = $request.Headers['Host']
                Origin = $request.Headers['Origin']; FetchSite = $request.Headers['Sec-Fetch-Site']
                Path = $path; ContentType = $request.ContentType
                PresentedToken = $request.Headers['X-ScavLife-Token']
                ExpectedAuthority = $consoleAuthority; ExpectedOrigin = $consoleOrigin
                ExpectedToken = $apiToken
            }
            $policyStatus = Get-ConsoleRequestStatus @policy
            if ($policyStatus -ne 200) {
                Write-JsonResponse -Response $response -StatusCode $policyStatus -Data @{ ok = $false; error = 'Request rejected by local console policy.' }
                continue
            }

            if ($path -eq "/api/config") {
                Write-JsonResponse -Response $response -Data @{
                    ok = $true
                    listenPrefix = $ListenPrefix
                    sptBaseUrl = $SptBaseUrl
                    profileId = $ProfileId
                    apiToken = $apiToken
                    mutationsEnabled = [bool]$EnableMutations
                    serverUnixTime = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
                }
                continue
            }

            if ($path -eq "/api/dashboard/overview") {
                $requestedProfileId = $ProfileId
                if ($request.HttpMethod -eq "POST") {
                    $requestText = Read-RequestText -Request $request
                    if (-not [string]::IsNullOrWhiteSpace($requestText)) {
                        $body = $requestText | ConvertFrom-Json -AsHashtable
                        if ($body -and $body.ContainsKey("profileId") -and -not [string]::IsNullOrWhiteSpace([string]$body["profileId"])) {
                            $requestedProfileId = [string]$body["profileId"]
                        }
                    }
                }

                Write-JsonResponse -Response $response -Data (Get-DashboardOverview -RequestedProfileId $requestedProfileId)
                continue
            }

            if ($routeMap.ContainsKey($path)) {
                if ($request.HttpMethod -ne "POST") {
                    Write-JsonResponse -Response $response -StatusCode 405 -Data @{
                        ok = $false
                        error = "Use POST for $path."
                    }
                    continue
                }

                if ($path -in $mutationRoutes -and -not $EnableMutations) {
                    Write-JsonResponse -Response $response -StatusCode 403 -Data @{ ok = $false; error = 'State changes are disabled. Restart with -EnableMutations only for a backed-up test profile.' }
                    continue
                }

                $requestText = Read-RequestText -Request $request
                $body = @{}
                if (-not [string]::IsNullOrWhiteSpace($requestText)) {
                    $body = $requestText | ConvertFrom-Json -AsHashtable
                    if ($null -eq $body) {
                        $body = @{}
                    }
                }

                if (-not $body.ContainsKey("profileId") -or [string]::IsNullOrWhiteSpace([string]$body["profileId"])) {
                    $body["profileId"] = $ProfileId
                }

                if ([string]$body["profileId"] -notmatch '^[A-Za-z0-9_-]{1,64}$') { throw 'Invalid profile ID.' }
                $data = Invoke-SptRoute -Path $routeMap[$path] -Body $body
                Write-JsonResponse -Response $response -Data @{
                    ok = $true
                    route = $path
                    data = $data
                }
                continue
            }

            $relativePath = [Uri]::UnescapeDataString($path.TrimStart("/"))
            if ([string]::IsNullOrWhiteSpace($relativePath)) {
                $relativePath = "index.html"
            }

            $candidatePath = Join-Path $webRoot $relativePath
            $resolvedPath = [System.IO.Path]::GetFullPath($candidatePath)
            $resolvedRoot = [System.IO.Path]::GetFullPath($webRoot).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar

            if (-not $resolvedPath.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
                Write-JsonResponse -Response $response -StatusCode 403 -Data @{ ok = $false; error = "Forbidden" }
                continue
            }

            if (-not (Test-Path -LiteralPath $resolvedPath -PathType Leaf)) {
                Write-JsonResponse -Response $response -StatusCode 404 -Data @{ ok = $false; error = "Not found" }
                continue
            }

            $bytes = [System.IO.File]::ReadAllBytes($resolvedPath)
            Write-BytesResponse -Response $response -Bytes $bytes -ContentType (Get-ContentType $resolvedPath)
        }
        catch {
            Write-JsonResponse -Response $response -StatusCode 500 -Data @{
                ok = $false
                error = $_.Exception.Message
                type = $_.Exception.GetType().FullName
            }
        }
    }
}
finally {
    $listener.Stop()
    $listener.Close()
}
