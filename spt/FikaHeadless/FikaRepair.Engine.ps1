# SPDX-License-Identifier: MIT
# Repair-only helpers. Installer and plugin-pruning behavior is unchanged.
Set-StrictMode -Version Latest

if (-not ('OutlandsFika.NativeFile' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
namespace OutlandsFika {
    [StructLayout(LayoutKind.Sequential)] public struct FileInfo {
        public uint Attributes; public System.Runtime.InteropServices.ComTypes.FILETIME Creation, Access, Write;
        public uint Volume, SizeHigh, SizeLow, Links, IndexHigh, IndexLow;
    }
    public static class NativeFile {
        [DllImport("kernel32.dll", SetLastError=true)]
        public static extern bool GetFileInformationByHandle(SafeFileHandle handle, out FileInfo info);
    }
}
'@
}

function Assert-RepairHandle {
    param([IO.FileStream] $Stream)
    $info = New-Object OutlandsFika.FileInfo
    if (-not [OutlandsFika.NativeFile]::GetFileInformationByHandle($Stream.SafeFileHandle, [ref]$info) -or $info.Links -ne 1) { throw 'File information unavailable or multiple hard links are unsupported.' }
    if ($Stream.Length -gt 1048576) { throw 'Configuration exceeds the 1 MiB limit.' }
}

function Assert-RepairVolume {
    param([string] $Root)
    if ($Root -notmatch '^[A-Za-z]:\\' -or $Root.Substring(2).Contains(':')) { throw 'Use normal local drive paths, without alternate streams.' }
    $drive = New-Object IO.DriveInfo([IO.Path]::GetPathRoot($Root))
    if ($drive.DriveType -ne 'Fixed' -or $drive.DriveFormat -ne 'NTFS') { throw 'Repair supports fixed local NTFS volumes only.' }
}

function Get-RepairHash {
    param([byte[]] $Bytes)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($Bytes))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
}

function Read-RepairBytes {
    param([string] $Path)
    Assert-SafeFile $Path
    $stream = [IO.File]::Open($Path, 'Open', 'Read', 'Read')
    try {
        Assert-RepairHandle $stream
        $bytes = New-Object byte[] ([int]$stream.Length)
        $offset = 0
        while ($offset -lt $bytes.Length) {
            $n = $stream.Read($bytes, $offset, $bytes.Length - $offset)
            if ($n -eq 0) { throw 'Short configuration read.' }
            $offset += $n
        }
        return ,$bytes
    } finally { $stream.Dispose() }
}

function Convert-RepairText {
    param([byte[]] $Bytes)
    $offset = 0
    if ($Bytes.Length -ge 3 -and $Bytes[0] -eq 239 -and $Bytes[1] -eq 187 -and $Bytes[2] -eq 191) { $offset = 3 }
    $utf8 = New-Object Text.UTF8Encoding($false, $true)
    $text = $utf8.GetString($Bytes, $offset, $Bytes.Length - $offset)
    if ($text.Contains([char]0)) { throw 'NUL in configuration.' }
    return [pscustomobject]@{ Text = $text; Bom = ($offset -eq 3) }
}

function Convert-RepairBytes {
    param([string] $Text, [bool] $Bom = $false)
    $utf8 = New-Object Text.UTF8Encoding($Bom, $true)
    return ,([byte[]]($utf8.GetPreamble() + $utf8.GetBytes($Text)))
}

function Edit-RepairJson {
    param([string] $Text, [string] $ProfileId, [string] $Endpoint)
    if ($Text.Trim().Length -eq 0 -or -not $Text.TrimStart().StartsWith('{')) { throw 'Expected a JSON object.' }
    # Reject comments, invalid escapes, duplicate keys and excessive nesting on
    # both editions. The platform parser validates grammar, not output bytes.
    $pattern = '\G(?:[ \t\r\n]+|"(?:[^"\\\x00-\x1f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*"|-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?|true|false|null|[{}\[\],:])'
    $lexer = New-Object Text.RegularExpressions.Regex($pattern, [Text.RegularExpressions.RegexOptions]::None, [TimeSpan]::FromSeconds(2))
    $tokens = New-Object 'Collections.Generic.List[object]'
    $position = 0
    while ($position -lt $Text.Length) {
        $match = $lexer.Match($Text, $position)
        if (-not $match.Success -or $match.Index -ne $position) { throw 'Unsupported or invalid JSON token.' }
        if (-not [string]::IsNullOrWhiteSpace($match.Value)) { $tokens.Add([pscustomobject]@{ Value = $match.Value; Start = $position; Length = $match.Length }) }
        if ($tokens.Count -gt 32768) { throw 'JSON token limit exceeded.' }
        $position += $match.Length
    }
    $stack = New-Object 'Collections.Generic.List[object]'
    $root = @{}
    for ($i = 0; $i -lt $tokens.Count; $i++) {
        $token = $tokens[$i]
        if ($token.Value -in '{','[') {
            $stack.Add([pscustomobject]@{ Kind = $token.Value; Keys = (New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)) })
            if ($stack.Count -gt 24) { throw 'JSON nesting limit exceeded.' }
        } elseif ($token.Value -in '}',']') {
            if ($stack.Count -eq 0) { throw 'Invalid JSON nesting.' }
            if ($i -gt 0 -and $tokens[$i - 1].Value -eq ',') { throw 'Trailing JSON commas are unsupported.' }
            $stack.RemoveAt($stack.Count - 1)
        } elseif ($token.Value.StartsWith('"') -and $i + 1 -lt $tokens.Count -and $tokens[$i + 1].Value -eq ':') {
            if ($stack.Count -eq 0 -or $stack[$stack.Count - 1].Kind -ne '{') { throw 'Invalid JSON property.' }
            $key = ConvertFrom-Json -InputObject ('[' + $token.Value + ']')
            if (-not $stack[$stack.Count - 1].Keys.Add([string]$key)) { throw 'Duplicate JSON property.' }
            if ($stack.Count -eq 1) { $root[[string]$key] = $i + 2 }
        }
    }
    $null = ConvertFrom-Json -InputObject $Text -ErrorAction Stop
    $changes = New-Object 'Collections.Generic.List[object]'
    $wanted = [ordered]@{ ProfileId = ($ProfileId | ConvertTo-Json -Compress); BackendUrl = ($Endpoint | ConvertTo-Json -Compress) }
    $missing = New-Object 'Collections.Generic.List[string]'
    foreach ($key in $wanted.Keys) {
        if ($root.ContainsKey($key)) {
            $index = $root[$key]
            $decoded = ConvertFrom-Json -InputObject ('[' + $tokens[$index - 2].Value + ']')
            if ([string]$decoded -cne $key -or -not $tokens[$index].Value.StartsWith('"')) { throw 'Selected JSON property has unexpected spelling or type.' }
            $changes.Add([pscustomobject]@{ Start = $tokens[$index].Start; Length = $tokens[$index].Length; Value = $wanted[$key] })
        } else { $missing.Add(('"' + $key + '": ' + $wanted[$key])) }
    }
    if ($root.ContainsKey('StartMinimized')) {
        $index = $root['StartMinimized']
        $decoded = ConvertFrom-Json -InputObject ('[' + $tokens[$index - 2].Value + ']')
        if ([string]$decoded -cne 'StartMinimized' -or $tokens[$index].Value -notin 'true','false') { throw 'StartMinimized must be a canonical boolean property.' }
    } else { $missing.Add('"StartMinimized": false') }
    if ($missing.Count -gt 0) {
        $prefix = if ($root.Count -gt 0) { ',' } else { '' }
        $changes.Add([pscustomobject]@{ Start = $tokens[$tokens.Count - 1].Start; Length = 0; Value = ($prefix + ($missing -join ',')) })
    }
    foreach ($change in ($changes | Sort-Object Start -Descending)) { $Text = $Text.Remove($change.Start, $change.Length).Insert($change.Start, $change.Value) }
    return $Text
}

function New-RepairEntry {
    param([string] $Root, [string] $Relative, [string] $Kind, [hashtable] $Settings)
    $path = Join-Path $Root $Relative
    Assert-SafeFile $path
    $exists = Test-Path -LiteralPath $path -PathType Leaf
    $before = [byte[]]@(); if ($exists) { $before = Read-RepairBytes $path }
    $decoded = Convert-RepairText $before
    if ($Kind -eq 'json') {
        $source = if ($exists) { $decoded.Text } else { '{}' }
        $afterText = Edit-RepairJson $source $Settings.ProfileId $Settings.Endpoint
    } else {
        if (-not $exists) { throw 'Selected Fika core configuration is missing.' }
        $afterText = $decoded.Text
        foreach ($key in @('Force IP', 'Force Bind IP', 'UDP Port')) {
            $pattern = '(?m)^([ \t]*' + [regex]::Escape($key) + '[ \t]*=[ \t]*)[^\r\n]*'
            if ([regex]::Matches($afterText, $pattern).Count -ne 1) { throw "Expected exactly one '$key' setting." }
            $value = [string]$Settings[$key]
            $afterText = [regex]::Replace($afterText, $pattern, [Text.RegularExpressions.MatchEvaluator]{ param($m) $m.Groups[1].Value + $value }.GetNewClosure())
        }
    }
    $after = Convert-RepairBytes $afterText $decoded.Bom
    if ($after.Length -gt 1048576) { throw 'Updated configuration exceeds the size limit.' }
    return [pscustomobject]@{ Path = $path; Relative = $Relative; Existed = $exists; Before = $before; After = $after; BeforeHash = (Get-RepairHash $before); AfterHash = (Get-RepairHash $after) }
}

function Get-RepairPlan {
    param([string] $Main, [string] $Headless, [string] $ProfileId, [uri] $BackendUrl,
          [string] $ForceIp, [string] $BindIp, [int] $UdpPort, [bool] $IncludeMainClient)
    $mainRoot = Get-SafeDirectory $Main -MustExist
    $headlessRoot = Get-SafeDirectory $Headless -MustExist
    Assert-SeparateDirectories $mainRoot $headlessRoot
    Assert-RepairVolume $mainRoot
    Assert-RepairVolume $headlessRoot
    if ($ProfileId -notmatch '^[A-Za-z0-9_-]{1,128}$' -or $UdpPort -lt 1 -or $UdpPort -gt 65535) { throw 'Invalid profile or port.' }
    Assert-IpSetting $ForceIp
    Assert-IpSetting $BindIp
    if ($ForceIp -match '[\r\n]' -or $BindIp -match '[\r\n]') { throw 'Invalid IP setting.' }
    if (-not $BackendUrl.IsAbsoluteUri -or $BackendUrl.Scheme -notin 'http','https' -or $BackendUrl.UserInfo -or $BackendUrl.Query -or $BackendUrl.Fragment -or $BackendUrl.AbsolutePath -ne '/') { throw 'BackendUrl must be an HTTP(S) origin without credentials, query, fragment or path.' }
    $profile = Join-Path $mainRoot ("SPT\user\profiles\$ProfileId.json")
    Assert-SafeFile $profile
    if (-not (Test-Path -LiteralPath $profile -PathType Leaf)) { throw 'Explicitly selected profile must exist; its contents are not read.' }
    $settings = @{ ProfileId = $ProfileId; Endpoint = $BackendUrl.AbsoluteUri.TrimEnd('/'); 'Force IP' = $ForceIp; 'Force Bind IP' = $BindIp; 'UDP Port' = $UdpPort }
    $entries = @(
        (New-RepairEntry $headlessRoot 'BepInEx\config\com.fika.core.cfg' 'ini' $settings),
        (New-RepairEntry $headlessRoot 'HeadlessConfig.json' 'json' $settings),
        (New-RepairEntry $mainRoot "SPT\user\mods\fika-server\assets\scripts\$ProfileId\HeadlessConfig.json" 'json' $settings)
    )
    if ($IncludeMainClient) { $entries += New-RepairEntry $mainRoot 'BepInEx\config\com.fika.core.cfg' 'ini' $settings }
    for ($i = 0; $i -lt $entries.Count; $i++) {
        $label = if ($i -ge 2) { 'Main' } else { 'Headless' }
        $entries[$i] | Add-Member -NotePropertyName Root -NotePropertyValue $label
    }
    return [pscustomobject]@{ Main = $mainRoot; Headless = $headlessRoot; ProfileId = $ProfileId; IncludeMainClient = $IncludeMainClient; Entries = $entries }
}

function Write-NewRepairFile {
    param([string] $Path, [byte[]] $Bytes)
    $stream = [IO.File]::Open($Path, 'CreateNew', 'Write', 'None')
    try { $stream.Write($Bytes, 0, $Bytes.Length); $stream.Flush($true) }
    finally { $stream.Dispose() }
}

function Invoke-RepairPlan {
    param($Plan)
    $backupParent = Join-Path $Plan.Headless '_outlands_backups'
    $null = Get-SafeDirectory $backupParent
    $backupRoot = Join-Path $backupParent ([guid]::NewGuid().ToString('N'))
    $handles = New-Object 'Collections.Generic.List[object]'
    try {
        foreach ($entry in $Plan.Entries) {
            Assert-SafeFile $entry.Path
            if ($entry.Existed) {
                $stream = [IO.File]::Open($entry.Path, 'Open', 'ReadWrite', 'None')
                $handles.Add([pscustomobject]@{ Entry = $entry; Stream = $stream })
                Assert-RepairHandle $stream
                if ($stream.Length -ne $entry.Before.Length) { throw 'Configuration changed since planning.' }
                $current = New-Object byte[] $entry.Before.Length
                $offset = 0
                while ($offset -lt $current.Length) {
                    $n = $stream.Read($current, $offset, $current.Length - $offset)
                    if ($n -eq 0) { throw 'Short locked read.' }; $offset += $n
                }
                if ((Get-RepairHash $current) -ne $entry.BeforeHash) { throw 'Configuration changed since planning.' }
            } elseif (Test-Path -LiteralPath $entry.Path) { throw 'A previously absent configuration appeared.' }
        }
        $null = New-Item -ItemType Directory -Path $backupRoot
        $records = @()
        $index = 0
        foreach ($entry in $Plan.Entries) {
            $name = if ($entry.Existed) { "$index.original" } else { $null }
            if ($entry.Existed) {
                $backup = Join-Path $backupRoot $name
                Write-NewRepairFile $backup $entry.Before
                if ((Get-RepairHash (Read-RepairBytes $backup)) -ne $entry.BeforeHash) { throw 'Backup verification failed; no configurations written.' }
            }
            $records += [ordered]@{ Root = $entry.Root; Relative = $entry.Relative; Existed = $entry.Existed; Backup = $name; BeforeHash = $entry.BeforeHash; AfterHash = $entry.AfterHash }
            $index++
        }
        $manifest = [ordered]@{ SchemaVersion = 1; Main = $Plan.Main; Headless = $Plan.Headless; ProfileId = $Plan.ProfileId; IncludeMainClient = $Plan.IncludeMainClient; Entries = $records }
        Write-NewRepairFile (Join-Path $backupRoot 'manifest.json') (Convert-RepairBytes ($manifest | ConvertTo-Json -Depth 8))
        # Verified original bytes and recovery manifest exist before first write.
        foreach ($entry in $Plan.Entries) {
            if (-not $entry.Existed) {
                $null = Get-SafeDirectory (Split-Path -Parent $entry.Path)
                $null = New-Item -ItemType Directory -Path (Split-Path -Parent $entry.Path) -Force
                $stream = [IO.File]::Open($entry.Path, 'CreateNew', 'ReadWrite', 'None')
                $handles.Add([pscustomobject]@{ Entry = $entry; Stream = $stream })
            }
            $handle = @($handles | Where-Object { $_.Entry.Path -eq $entry.Path })[0]
            $handle.Stream.Position = 0
            $handle.Stream.Write($entry.After, 0, $entry.After.Length)
            $handle.Stream.SetLength($entry.After.Length)
            $handle.Stream.Flush($true)
            $handle.Stream.Position = 0
            $observed = New-Object byte[] $entry.After.Length
            $offset = 0
            while ($offset -lt $observed.Length) {
                $n = $handle.Stream.Read($observed, $offset, $observed.Length - $offset)
                if ($n -eq 0) { throw 'Short write verification read.' }; $offset += $n
            }
            if ((Get-RepairHash $observed) -ne $entry.AfterHash) { throw 'Configuration write verification failed.' }
        }
        return $backupRoot
    } catch { throw "Repair failed. If created, retain the private recovery directory '$backupRoot'. Multi-file changes may be incomplete. $($_.Exception.Message)" }
    finally { foreach ($handle in $handles) { $handle.Stream.Dispose() } }
}

function Get-RestorePlan {
    param([string] $BackupDirectory, [string] $Main, [string] $Headless)
    $directory = Get-SafeDirectory $BackupDirectory -MustExist
    $mainRoot = Get-SafeDirectory $Main -MustExist
    $headlessRoot = Get-SafeDirectory $Headless -MustExist
    Assert-SeparateDirectories $mainRoot $headlessRoot
    Assert-RepairVolume $mainRoot
    Assert-RepairVolume $headlessRoot
    $text = (Convert-RepairText (Read-RepairBytes (Join-Path $directory 'manifest.json'))).Text
    $null = Edit-RepairJson $text 'unused' 'https://127.0.0.1:6969'
    $manifest = ConvertFrom-Json -InputObject $text
    if ($manifest.SchemaVersion -ne 1 -or $manifest.Main -cne $mainRoot -or $manifest.Headless -cne $headlessRoot -or $manifest.ProfileId -notmatch '^[A-Za-z0-9_-]{1,128}$' -or $manifest.IncludeMainClient -isnot [bool]) { throw 'Recovery manifest/root mismatch.' }
    $expected = @(
        @('Headless', 'BepInEx\config\com.fika.core.cfg'),
        @('Headless', 'HeadlessConfig.json'),
        @('Main', "SPT\user\mods\fika-server\assets\scripts\$($manifest.ProfileId)\HeadlessConfig.json")
    )
    if ($manifest.IncludeMainClient) { $expected += ,@('Main', 'BepInEx\config\com.fika.core.cfg') }
    if (@($manifest.Entries).Count -ne $expected.Count) { throw 'Unexpected recovery entry count.' }
    $entries = @()
    for ($i = 0; $i -lt $expected.Count; $i++) {
        $record = $manifest.Entries[$i]
        if ($record.Root -cne $expected[$i][0] -or $record.Relative -cne $expected[$i][1] -or $record.Existed -isnot [bool] -or $record.BeforeHash -cnotmatch '^[a-f0-9]{64}$' -or $record.AfterHash -cnotmatch '^[a-f0-9]{64}$') { throw 'Invalid recovery entry.' }
        $root = if ($record.Root -eq 'Main') { $mainRoot } else { $headlessRoot }
        $path = Join-Path $root $record.Relative
        Assert-SafeFile $path
        $before = [byte[]]@()
        if ($record.Existed) {
            if ($record.Backup -cne "$i.original") { throw 'Invalid backup filename.' }
            $before = Read-RepairBytes (Join-Path $directory $record.Backup)
        } elseif ($null -ne $record.Backup) { throw 'Unexpected backup for a new file.' }
        if ((Get-RepairHash $before) -cne $record.BeforeHash) { throw 'Original backup hash mismatch.' }
        $exists = Test-Path -LiteralPath $path -PathType Leaf
        $current = [byte[]]@(); if ($exists) { $current = Read-RepairBytes $path }
        $currentHash = Get-RepairHash $current
        if ($exists) {
            if ($currentHash -cne $record.AfterHash -and -not ($record.Existed -and $currentHash -ceq $record.BeforeHash)) { throw 'Configuration changed after repair; refusing to overwrite it.' }
        } elseif ($record.Existed) { throw 'Previously existing configuration is now missing.' }
        $entries += [pscustomobject]@{ Path = $path; Existed = $record.Existed; CurrentExists = $exists; CurrentHash = $currentHash; Before = $before; BeforeHash = $record.BeforeHash }
    }
    return $entries
}

function Invoke-RepairRestore {
    param([object[]] $Entries)
    $handles = New-Object 'Collections.Generic.List[object]'
    try {
        foreach ($entry in $Entries) {
            Assert-SafeFile $entry.Path
            if ($entry.CurrentExists) {
                $stream = [IO.File]::Open($entry.Path, 'Open', 'ReadWrite', 'None')
                $handles.Add([pscustomobject]@{ Entry = $entry; Stream = $stream })
                Assert-RepairHandle $stream
                $bytes = New-Object byte[] ([int]$stream.Length)
                $offset = 0
                while ($offset -lt $bytes.Length) {
                    $n = $stream.Read($bytes, $offset, $bytes.Length - $offset)
                    if ($n -eq 0) { throw 'Short restore read.' }; $offset += $n
                }
                if ((Get-RepairHash $bytes) -cne $entry.CurrentHash) { throw 'Restore target changed since preview.' }
            } elseif (Test-Path -LiteralPath $entry.Path) { throw 'Restore target appeared since preview.' }
        }
        foreach ($handle in $handles) {
            if ($handle.Entry.Existed) {
                $handle.Stream.Position = 0
                $bytes = $handle.Entry.Before
                $handle.Stream.Write($bytes, 0, $bytes.Length)
                $handle.Stream.SetLength($bytes.Length)
                $handle.Stream.Flush($true)
            }
        }
    } finally { foreach ($handle in $handles) { $handle.Stream.Dispose() } }
    foreach ($entry in $Entries) {
        if (-not $entry.Existed -and $entry.CurrentExists) {
            Assert-SafeFile $entry.Path
            if ((Get-RepairHash (Read-RepairBytes $entry.Path)) -cne $entry.CurrentHash) { throw 'New file changed before removal.' }
            [IO.File]::Delete($entry.Path)
        } elseif ($entry.Existed) {
            if ((Get-RepairHash (Read-RepairBytes $entry.Path)) -cne $entry.BeforeHash) { throw 'Restore verification failed.' }
        }
    }
}
