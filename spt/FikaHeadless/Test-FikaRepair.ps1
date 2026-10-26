# SPDX-License-Identifier: MIT
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Run the native repair checks on Windows.' }
. (Join-Path $PSScriptRoot 'FikaHeadless.Common.ps1')
. (Join-Path $PSScriptRoot 'FikaRepair.Engine.ps1')
$work = Join-Path $PSScriptRoot ('.test-repair-' + [guid]::NewGuid().ToString('N'))
$script:passed = 0
$repair = Join-Path $PSScriptRoot 'Repair-FikaHeadlessConfig.ps1'
$restore = Join-Path $PSScriptRoot 'Restore-FikaHeadlessConfig.ps1'

function Assert { param([bool] $Value, [string] $Why); if (-not $Value) { throw $Why } }
function Reject { param([scriptblock] $Action); $failed = $false; try { & $Action | Out-Null } catch { $failed = $true }; Assert $failed 'Expected rejection.' }
function Snapshot {
    param([string] $Directory)
    return (@(Get-ChildItem -LiteralPath $Directory -Recurse -Force -File | Sort-Object FullName | ForEach-Object { $_.FullName.Substring($Directory.Length) + ':' + (Get-FileHash -LiteralPath $_.FullName).Hash }) -join "`n")
}
function Put { param([string] $Path, [string] $Text); $null = New-Item -ItemType Directory -Path (Split-Path -Parent $Path) -Force; [IO.File]::WriteAllBytes($Path, (Convert-RepairBytes $Text)) }
function Fixture {
    $case = Join-Path $work ([guid]::NewGuid().ToString('N'))
    $main = Join-Path $case 'Main'
    $headless = Join-Path $case 'Headless'
    $profile = 'fictional_headless'
    $core = 'Force IP = Disabled' + "`r`nForce Bind IP = Disabled`r`nUDP Port = 1`r`nOther = keep`r`n"
    Put (Join-Path $main "SPT\user\profiles\$profile.json") 'FICTIONAL profile marker: intentionally not valid JSON; contents must never be read'
    Put (Join-Path $headless 'BepInEx\config\com.fika.core.cfg') $core
    Put (Join-Path $main 'BepInEx\config\com.fika.core.cfg') $core
    $options = @{ MainSptRoot = $main; HeadlessRoot = $headless; ProfileId = $profile; BackendUrl = 'https://127.0.0.1:6969'; ForceIp = '192.0.2.42'; BindIp = 'Disabled'; UdpPort = 25565 }
    return [pscustomobject]@{ Root = $case; Main = $main; Headless = $headless; Core = (Join-Path $headless 'BepInEx\config\com.fika.core.cfg'); Launch = (Join-Path $headless 'HeadlessConfig.json'); Server = (Join-Path $main "SPT\user\mods\fika-server\assets\scripts\$profile\HeadlessConfig.json"); Args = $options }
}
function Plan { param($f, [bool] $Include = $false); return Get-RepairPlan $f.Main $f.Headless $f.Args.ProfileId ([uri]$f.Args.BackendUrl) $f.Args.ForceIp $f.Args.BindIp $f.Args.UdpPort $Include }
function Run-Case {
    param([string] $Name, [scriptblock] $Action)
    & $Action
    $script:passed++
    Write-Output "PASS: $Name"
}

try {
    $null = New-Item -ItemType Directory -Path $work
    Run-Case 'preview and WhatIf create no files or directories' {
        $f = Fixture; $before = Snapshot $f.Root
        $dirs = @(Get-ChildItem -LiteralPath $f.Root -Recurse -Directory).Count
        $options = $f.Args; & $repair @options | Out-Null
        $options = $f.Args; & $repair @options -Apply -WhatIf | Out-Null
        Assert ((Snapshot $f.Root) -ceq $before) 'Preview modified files.'
        Assert (@(Get-ChildItem -LiteralPath $f.Root -Recurse -Directory).Count -eq $dirs) 'Preview created directories.'
    }
    Run-Case 'repair and restore preserve originals, new-file absence and opt-in main client' {
        $f = Fixture; $before = Snapshot $f.Root
        $options = $f.Args; & $repair @options -IncludeMainClient -Apply -Confirm:$false | Out-Null
        $mainCore = [IO.File]::ReadAllText((Join-Path $f.Main 'BepInEx\config\com.fika.core.cfg'))
        Assert ($mainCore.Contains('192.0.2.42')) 'Opt-in main settings not changed.'
        $backup = @(Get-ChildItem -LiteralPath (Join-Path $f.Headless '_outlands_backups') -Directory)[0].FullName
        $restoreArgs = @{ MainSptRoot = $f.Main; HeadlessRoot = $f.Headless; BackupDirectory = $backup }
        $after = Snapshot $f.Root
        & $restore @restoreArgs | Out-Null
        & $restore @restoreArgs -Apply -WhatIf | Out-Null
        Assert ((Snapshot $f.Root) -ceq $after) 'Restore preview changed files.'
        & $restore @restoreArgs -Apply -Confirm:$false | Out-Null
        Assert (-not (Test-Path -LiteralPath $f.Launch)) 'New headless file was not removed.'
        Assert (-not (Test-Path -LiteralPath $f.Server)) 'New server file was not removed.'
        $originalLines = @((Snapshot $f.Root) -split "`n" | Where-Object { $_ -notmatch '_outlands_backups' }) -join "`n"
        Assert ($originalLines -ceq $before) 'Original files were not restored byte-for-byte.'
        & $restore @restoreArgs -Apply -Confirm:$false | Out-Null
    }
    Run-Case 'JSON preserves unrelated exact text, nested keys, large numbers, BOM and StartMinimized' {
        $f = Fixture
        $source = '{ "ProfileId":"old", "BackendUrl":"https://example.invalid", "StartMinimized":true, "exact":900719925474099312345678901234567890, "nested":{"BackendUrl":"keep","str":"a\\b\"c"} }'
        [IO.File]::WriteAllBytes($f.Launch, (Convert-RepairBytes $source $true))
        Put $f.Server '{"Other":{"x":[true,null,"fictional"]}}'
        $before = Snapshot $f.Root; $plan = Plan $f
        $backup = Invoke-RepairPlan $plan
        $result = (Convert-RepairText (Read-RepairBytes $f.Launch))
        Assert $result.Bom 'BOM changed.'
        Assert ($result.Text.Contains('"exact":900719925474099312345678901234567890')) 'Unknown numeric text changed.'
        Assert ($result.Text.Contains('"nested":{"BackendUrl":"keep","str":"a\\b\"c"}')) 'Nested data changed.'
        Assert ($result.Text.Contains('"StartMinimized":true')) 'Minimized preference changed.'
        Invoke-RepairRestore @(Get-RestorePlan $backup $f.Main $f.Headless)
        $withoutBackups = @((Snapshot $f.Root) -split "`n" | Where-Object { $_ -notmatch '_outlands_backups' }) -join "`n"
        Assert ($withoutBackups -ceq $before) 'Existing JSON not restored exactly.'
    }
    Run-Case 'idempotent repair and unchanged main client by default' {
        $f = Fixture; $mainCore = Join-Path $f.Main 'BepInEx\config\com.fika.core.cfg'; $hash = (Get-FileHash -LiteralPath $mainCore).Hash
        $null = Invoke-RepairPlan (Plan $f)
        $again = Plan $f
        Assert (@($again.Entries | Where-Object { $_.BeforeHash -cne $_.AfterHash }).Count -eq 0) 'Repair is not idempotent.'
        Assert ((Get-FileHash -LiteralPath $mainCore).Hash -ceq $hash) 'Main config changed without opt-in.'
    }
    foreach ($bad in @('{"x":1,"x":2}', '{"x":{"a":1,"A":2}}', '{"ProfileId":"x","profileid":"y"}', '{"ProfileId":null}', '{"StartMinimized":"yes"}', '{"ProfileId":"x",}', '[]', '{"x":/*comment*/1}', '{"x":"\q"}', '{"x":1} trailing', '{"x": [1,]}')) {
        Run-Case 'invalid, ambiguous or unsupported JSON rejected without changes' {
            $f = Fixture; Put $f.Launch $bad; $before = Snapshot $f.Root
            Reject { $options = $f.Args; & $repair @options -Apply -Confirm:$false }
            Assert ((Snapshot $f.Root) -ceq $before) 'Rejected JSON changed files.'
        }
    }
    Run-Case 'escaped duplicate JSON keys rejected' { Reject { Edit-RepairJson '{"\u0078":1,"x":2}' 'demo' 'https://127.0.0.1:6969' } }
    Run-Case 'depth and token bounds' {
        Reject { Edit-RepairJson ('{"x":' + ('[' * 25) + '0' + (']' * 25) + '}') 'demo' 'https://127.0.0.1:6969' }
        Reject { Edit-RepairJson ('{"x":[' + ('0,' * 17000) + '0]}') 'demo' 'https://127.0.0.1:6969' }
    }
    Run-Case 'invalid UTF-8 and oversized input' {
        $f = Fixture; [IO.File]::WriteAllBytes($f.Launch, [byte[]]@(255,254)); Reject { Plan $f }
        [IO.File]::WriteAllBytes($f.Launch, (New-Object byte[] 1048577)); Reject { Plan $f }
    }
    Run-Case 'missing and duplicate INI settings' {
        $f = Fixture; Put $f.Core 'Other = keep'; Reject { Plan $f }
        Put $f.Core "Force IP = Disabled`nForce Bind IP = Disabled`nUDP Port = 1`nUDP Port = 2"; Reject { Plan $f }
    }
    foreach ($url in @('file:///D:/fictional','https://user:password@example.invalid','https://example.invalid/path','https://example.invalid/?token=fictional','https://example.invalid/#fictional')) {
        Run-Case 'invalid backend origin rejected' { $f = Fixture; $a = $f.Args.Clone(); $a.BackendUrl = $url; Reject { & $repair @a -Apply -Confirm:$false } }
    }
    Run-Case 'invalid profile, missing profile, overlap, port and IP' {
        $f = Fixture
        foreach ($edit in @(@{ ProfileId = '../escape' }, @{ ProfileId = 'missing' }, @{ HeadlessRoot = $f.Main }, @{ UdpPort = 0 }, @{ ForceIp = 'not-an-IP' })) {
            $a = $f.Args.Clone(); foreach ($key in $edit.Keys) { $a[$key] = $edit[$key] }; Reject { & $repair @a -Apply -Confirm:$false }
        }
    }
    Run-Case 'planned bytes must still match at apply' {
        $f = Fixture; $p = Plan $f; Put $f.Core "Force IP = Disabled`nForce Bind IP = Disabled`nUDP Port = 2"; $before = Snapshot $f.Root
        Reject { Invoke-RepairPlan $p }; Assert ((Snapshot $f.Root) -ceq $before) 'Stale plan changed files.'
    }
    Run-Case 'new destination appearing after plan rejected' {
        $f = Fixture; $p = Plan $f; Put $f.Launch '{}'; $before = Snapshot $f.Root
        Reject { Invoke-RepairPlan $p }; Assert ((Snapshot $f.Root) -ceq $before) 'Appeared target overwritten.'
    }
    Run-Case 'locked existing target prevents every write' {
        $f = Fixture; Put $f.Launch '{}'; $p = Plan $f; $before = Snapshot $f.Root
        $lock = [IO.File]::Open($f.Launch, 'Open', 'Read', 'None')
        try { Reject { Invoke-RepairPlan $p } } finally { $lock.Dispose() }
        Assert ((Snapshot $f.Root) -ceq $before) 'Lock failure caused partial repair.'
    }
    Run-Case 'hard-linked configuration rejected' {
        $f = Fixture; $alias = Join-Path $f.Root 'alias.cfg'
        $null = New-Item -ItemType HardLink -Path $alias -Target $f.Core
        Reject { Plan $f }
    }
    Run-Case 'directory junction rejected without following it' {
        $f = Fixture; $alias = Join-Path $f.Root 'LinkedMain'
        $null = New-Item -ItemType Junction -Path $alias -Target $f.Main
        try { $a = $f.Args.Clone(); $a.MainSptRoot = $alias; Reject { & $repair @a } }
        finally { [IO.Directory]::Delete($alias) }
    }
    Run-Case 'changed target stops restore before any changes' {
        $f = Fixture; $backup = Invoke-RepairPlan (Plan $f); Put $f.Server '{"new":"user change"}'; $before = Snapshot $f.Root
        Reject { & $restore -MainSptRoot $f.Main -HeadlessRoot $f.Headless -BackupDirectory $backup -Apply -Confirm:$false }
        Assert ((Snapshot $f.Root) -ceq $before) 'Changed target overwritten during restore.'
    }
    Run-Case 'corrupt backup stops restore' {
        $f = Fixture; $backup = Invoke-RepairPlan (Plan $f); Put (Join-Path $backup '0.original') 'corrupted'; $before = Snapshot $f.Root
        Reject { Get-RestorePlan $backup $f.Main $f.Headless }; Assert ((Snapshot $f.Root) -ceq $before) 'Corrupt backup changed files.'
    }
    Run-Case 'manifest traversal and root mismatch rejected' {
        $f = Fixture; $backup = Invoke-RepairPlan (Plan $f)
        Reject { Get-RestorePlan $backup $f.Headless $f.Main }
        $file = Join-Path $backup 'manifest.json'; $m = [IO.File]::ReadAllText($file) | ConvertFrom-Json
        $m.Entries[0].Relative = '..\escape.cfg'; Put $file ($m | ConvertTo-Json -Depth 8)
        Reject { Get-RestorePlan $backup $f.Main $f.Headless }
    }
    Run-Case 'restore stale plan rejected before writes' {
        $f = Fixture; $backup = Invoke-RepairPlan (Plan $f); $entries = @(Get-RestorePlan $backup $f.Main $f.Headless)
        Put $f.Core 'later edit'; $before = Snapshot $f.Root
        Reject { Invoke-RepairRestore $entries }; Assert ((Snapshot $f.Root) -ceq $before) 'Stale restore overwrote edit.'
    }
    Run-Case 'missing originally existing file is not silently recreated' {
        $f = Fixture; $backup = Invoke-RepairPlan (Plan $f); [IO.File]::Delete($f.Core)
        Reject { Get-RestorePlan $backup $f.Main $f.Headless }
    }
    Run-Case 'backup write failure leaves all configurations unchanged' {
        $f = Fixture; $p = Plan $f; $before = Snapshot $f.Root
        function Write-NewRepairFile { param([string] $Path, [byte[]] $Bytes); throw 'Synthetic backup I/O failure.' }
        Reject { Invoke-RepairPlan $p }
        Assert ((Snapshot $f.Root) -ceq $before) 'Backup failure changed a configuration.'
    }
    Run-Case 'fictional example creates only a new destination and repairs without a game' {
        $destination = Join-Path $work 'FictionalExample'
        & (Join-Path $PSScriptRoot 'Create-FikaRepairDemo.ps1') -Destination $destination | Out-Null
        Reject { & (Join-Path $PSScriptRoot 'Create-FikaRepairDemo.ps1') -Destination $destination }
        $a = @{ MainSptRoot = (Join-Path $destination 'Main'); HeadlessRoot = (Join-Path $destination 'Headless'); ProfileId = 'demo_headless'; BackendUrl = 'https://127.0.0.1:6969'; ForceIp = '192.0.2.42' }
        & $repair @a -Apply -Confirm:$false | Out-Null
        $json = [IO.File]::ReadAllText((Join-Path $destination 'Headless\HeadlessConfig.json')) | ConvertFrom-Json
        Assert ($json.FictionalNote -ceq 'keep this setting' -and $json.StartMinimized -eq $true) 'Demo preference was lost.'
    }
    Write-Output "PASS: $script:passed repair checks; PowerShell $($PSVersionTable.PSVersion). Fictional files only; no game, installer or network operation."
} finally {
    $full = [IO.Path]::GetFullPath($work)
    $prefix = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\') + '\'
    if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) -or -not (Split-Path -Leaf $full).StartsWith('.test-repair-')) { throw 'Unexpected fixture cleanup path.' }
    if (Test-Path -LiteralPath $full) { Remove-Item -LiteralPath $full -Recurse -Force }
}
