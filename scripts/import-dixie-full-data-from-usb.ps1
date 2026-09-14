[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PackageRoot,
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [switch]$InstallLocalEnv
)

$ErrorActionPreference = 'Stop'

function Copy-DirectoryContents {
    param([string]$Source, [string]$Destination)

    if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
        throw "Package directory not found: $Source"
    }
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    foreach ($item in Get-ChildItem -LiteralPath $Source -Force) {
        Copy-Item -LiteralPath $item.FullName -Destination $Destination -Recurse -Force
    }
}

$package = (Resolve-Path -LiteralPath $PackageRoot).Path
$repo = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not (Test-Path -LiteralPath (Join-Path $repo '.git') -PathType Container)) {
    throw "Not a Git repository: $repo"
}
if (-not (Test-Path -LiteralPath (Join-Path $package 'handoff-manifest.json') -PathType Leaf)) {
    throw "Missing handoff-manifest.json in package: $package"
}

$manifest = Get-Content -LiteralPath (Join-Path $package 'handoff-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.event_id -ne 'dixie_fire_2021') {
    throw "Unexpected package event: $($manifest.event_id)"
}

# Merge only data directories. Member C's code and environment directory are not changed.
Copy-DirectoryContents -Source (Join-Path $package 'data\raw') -Destination (Join-Path $repo 'data\raw')
Copy-DirectoryContents -Source (Join-Path $package 'data\processed') -Destination (Join-Path $repo 'data\processed')

$seedSource = Join-Path $package 'database\dixie_fire_2021_database_seed.sql'
if (-not (Test-Path -LiteralPath $seedSource -PathType Leaf)) {
    throw "Database seed missing: $seedSource"
}
$seedDestinationDirectory = Join-Path $repo 'data\local\database'
New-Item -ItemType Directory -Path $seedDestinationDirectory -Force | Out-Null
Copy-Item -LiteralPath $seedSource -Destination (Join-Path $seedDestinationDirectory 'dixie_fire_2021_database_seed.sql') -Force

if ($InstallLocalEnv) {
    $envSource = Join-Path $package 'local-config\.env'
    if (-not (Test-Path -LiteralPath $envSource -PathType Leaf)) {
        throw 'InstallLocalEnv was specified, but the package contains no local-config/.env.'
    }
    Copy-Item -LiteralPath $envSource -Destination (Join-Path $repo '.env') -Force
}

$sentinelDirectory = Join-Path $repo 'data\raw\sentinel2\dixie_fire_2021\gee'
$sentinelFiles = @(Get-ChildItem -LiteralPath $sentinelDirectory -File -Filter '*.tif')
if ($sentinelFiles.Count -ne 18) {
    throw "Import incomplete: expected 18 Sentinel GeoTIFFs, found $($sentinelFiles.Count)."
}
if (Get-ChildItem -LiteralPath $sentinelDirectory -File -Filter '*.download') {
    throw 'Invalid .download residue exists in the Sentinel directory.'
}

Write-Host "Data installed under: $(Join-Path $repo 'data')"
Write-Host "Database seed: $(Join-Path $seedDestinationDirectory 'dixie_fire_2021_database_seed.sql')"
Write-Host 'Member C code, branch, and environment directory were not modified.'

