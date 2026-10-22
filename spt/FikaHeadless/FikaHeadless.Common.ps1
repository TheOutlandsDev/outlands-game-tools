# SPDX-License-Identifier: MIT
Set-StrictMode -Version Latest

function Get-SafeDirectory {
    param([Parameter(Mandatory)][string] $Path, [switch] $MustExist)
    if ([string]::IsNullOrWhiteSpace($Path)) { throw 'Directory cannot be empty.' }
    $full = [IO.Path]::GetFullPath($Path).TrimEnd([IO.Path]::DirectorySeparatorChar)
    if ($full -eq [IO.Path]::GetPathRoot($full).TrimEnd([IO.Path]::DirectorySeparatorChar)) {
        throw 'A drive root is not an installation directory.'
    }
    if ($MustExist -and -not (Test-Path -LiteralPath $full -PathType Container)) {
        throw "Directory not found: $full"
    }
    if ((Test-Path -LiteralPath $full) -and -not (Test-Path -LiteralPath $full -PathType Container)) {
        throw "Expected a directory: $full"
    }
    $current = $full
    while ($current) {
        if (Test-Path -LiteralPath $current) {
            $item = Get-Item -LiteralPath $current -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Linked paths are unsupported for these helpers: $current"
            }
        }
        $parent = Split-Path -Parent $current
        if ($parent -eq $current) { break }
        $current = $parent
    }
    return $full
}

function Assert-SeparateDirectories {
    param([string] $First, [string] $Second)
    $a = $First.TrimEnd('\') + '\'
    $b = $Second.TrimEnd('\') + '\'
    if ($a.StartsWith($b, [StringComparison]::OrdinalIgnoreCase) -or
        $b.StartsWith($a, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Main and headless installations must be separate, non-overlapping directories.'
    }
}

function Assert-SafeFile {
    param([string] $Path)
    $null = Get-SafeDirectory -Path (Split-Path -Parent $Path)
    if (Test-Path -LiteralPath $Path) {
        $item = Get-Item -LiteralPath $Path -Force
        if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "Expected an unlinked file: $Path"
        }
    }
}

function Assert-IpSetting {
    param([string] $Value)
    $parsed = $null
    if ($Value -ne 'Disabled' -and -not [Net.IPAddress]::TryParse($Value, [ref] $parsed)) {
        throw 'ForceIp and BindIp must be IP addresses or Disabled.'
    }
}
