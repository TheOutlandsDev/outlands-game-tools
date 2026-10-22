$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'ConsoleSecurity.ps1')
$script:checks = 0
function Assert-Equal($Actual, $Expected, [string] $Name) {
    if ($Actual -cne $Expected) { throw "$Name expected '$Expected', received '$Actual'." }
    $script:checks++
}
function Assert-Rejected([string] $Url) {
    $rejected = $false
    try { $null = Get-LoopbackOrigin -Value $Url } catch { $rejected = $true }
    Assert-Equal $rejected $true "Reject $Url"
}
Assert-Equal (Get-LoopbackOrigin 'http://127.0.0.1:7777/') 'http://127.0.0.1:7777' 'Loopback origin'
Assert-Equal (Get-LoopbackOrigin 'https://[::1]:6969/') 'https://[::1]:6969' 'IPv6 loopback'
foreach ($url in @('http://localhost:7777/', 'http://0.0.0.0:7777/', 'http://192.0.2.1/', 'https://example.com/', 'http://127.0.0.1:7777/path', 'http://user:pass@127.0.0.1/', 'http://127.0.0.1/?x=1', 'http://127.0.0.1/#x', 'ftp://127.0.0.1/')) { Assert-Rejected $url }
$valid = @{
    Method = 'POST'; HostHeader = '127.0.0.1:7777'; Origin = 'http://127.0.0.1:7777'
    FetchSite = 'same-origin'; Path = '/api/scavlife/status'; ContentType = 'application/json'
    PresentedToken = 'test-token'; ExpectedAuthority = '127.0.0.1:7777'
    ExpectedOrigin = 'http://127.0.0.1:7777'; ExpectedToken = 'test-token'
}
Assert-Equal (Get-ConsoleRequestStatus @valid) 200 'Same-origin JSON token request'
$cases = @(
    @{ Key = 'HostHeader'; Value = 'attacker.invalid:7777'; Status = 403 },
    @{ Key = 'Origin'; Value = 'https://attacker.invalid'; Status = 403 },
    @{ Key = 'Origin'; Value = ''; Status = 403 },
    @{ Key = 'Origin'; Value = 'null'; Status = 403 },
    @{ Key = 'FetchSite'; Value = 'cross-site'; Status = 403 },
    @{ Key = 'PresentedToken'; Value = ''; Status = 403 },
    @{ Key = 'PresentedToken'; Value = 'TEST-TOKEN'; Status = 403 },
    @{ Key = 'ContentType'; Value = 'text/plain'; Status = 415 },
    @{ Key = 'Method'; Value = 'GET'; Status = 405 },
    @{ Key = 'Method'; Value = 'OPTIONS'; Status = 405 }
)
foreach ($case in $cases) {
    $argsCopy = $valid.Clone(); $argsCopy[$case.Key] = $case.Value
    Assert-Equal (Get-ConsoleRequestStatus @argsCopy) $case.Status "Policy $($case.Key)=$($case.Value)"
}
$config = $valid.Clone(); $config.Path = '/api/config'; $config.Method = 'GET'; $config.Origin = ''; $config.PresentedToken = ''
Assert-Equal (Get-ConsoleRequestStatus @config) 200 'Same-host config bootstrap'
$config.FetchSite = 'cross-site'
Assert-Equal (Get-ConsoleRequestStatus @config) 403 'Cross-site config bootstrap'
Write-Host "Passed $script:checks offline policy checks; no listener/backend started."
