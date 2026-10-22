# Pure request-policy helpers; dot-sourcing this file starts no listener.
function Get-LoopbackOrigin {
    param([string] $Value, [string[]] $AllowedSchemes = @('http', 'https'))
    $uri = [Uri]$Value
    $address = $null
    if (-not $uri.IsAbsoluteUri -or $uri.Scheme -notin $AllowedSchemes -or
        -not [Net.IPAddress]::TryParse($uri.DnsSafeHost, [ref]$address) -or
        -not [Net.IPAddress]::IsLoopback($address) -or $uri.UserInfo -or
        $uri.Query -or $uri.Fragment -or $uri.AbsolutePath -ne '/') {
        throw 'Use an HTTP(S) origin with a literal loopback IP, no credentials, and no path/query/fragment.'
    }
    return $uri.GetLeftPart([UriPartial]::Authority)
}

function Get-ConsoleRequestStatus {
    param(
        [string] $Method, [string] $HostHeader, [string] $Origin,
        [string] $FetchSite, [string] $Path, [string] $ContentType,
        [string] $PresentedToken, [string] $ExpectedAuthority,
        [string] $ExpectedOrigin, [string] $ExpectedToken
    )
    # Exact Host + Origin checks also reject DNS rebinding and browser cross-site calls.
    if ($HostHeader -ine $ExpectedAuthority -or $FetchSite -eq 'cross-site') { return 403 }
    if ($Origin -and $Origin -ine $ExpectedOrigin) { return 403 }
    if ($Method -eq 'OPTIONS') { return 405 }
    if ($Path -eq '/api/config') {
        if ($Method -ne 'GET') { return 405 }
        return 200
    }
    if ($Path.StartsWith('/api/', [StringComparison]::Ordinal)) {
        if ($Method -ne 'POST') { return 405 }
        if ($Origin -ine $ExpectedOrigin -or -not $ExpectedToken -or $PresentedToken -cne $ExpectedToken) { return 403 }
        if (($ContentType -split ';')[0].Trim() -ine 'application/json') { return 415 }
        return 200
    }
    if ($Method -ne 'GET') { return 405 }
    return 200
}
