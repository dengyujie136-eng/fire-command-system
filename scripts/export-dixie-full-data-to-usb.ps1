[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$DestinationRoot,
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$SentinelSource = (Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path 'data-sources\real'),
    [string]$SeedPath = (Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path '甲\dixie_fire_2021_database_seed.sql'),
    [switch]$IncludeLocalEnv
)

$ErrorActionPreference = 'Stop'

function Copy-DirectoryContents {
    param([string]$Source, [string]$Destination)

    if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
        throw "Source directory not found: $Source"
    }
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    foreach ($item in Get-ChildItem -LiteralPath $Source -Force) {
        Copy-Item -LiteralPath $item.FullName -Destination $Destination -Recurse -Force
    }
}

$repo = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not (Test-Path -LiteralPath (Join-Path $repo 'compose.yaml') -PathType Leaf)) {
    throw "Not a fire-command-system repository: $repo"
}

New-Item -ItemType Directory -Path $DestinationRoot -Force | Out-Null
$destination = (Resolve-Path -LiteralPath $DestinationRoot).Path
$destinationDriveRoot = [System.IO.Path]::GetPathRoot($destination).TrimEnd('\')
if ($destination.TrimEnd('\') -eq $destinationDriveRoot) {
    throw 'DestinationRoot must be a package directory, not a drive root.'
}
if ($destination.StartsWith($repo, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'The USB handoff package must be outside the Git repository.'
}

$packageData = Join-Path $destination 'data'
Copy-DirectoryContents -Source (Join-Path $repo 'data\raw') -Destination (Join-Path $packageData 'raw')
Copy-DirectoryContents -Source (Join-Path $repo 'data\processed') -Destination (Join-Path $packageData 'processed')

$sentinelFiles = @(Get-ChildItem -LiteralPath $SentinelSource -File -Filter '*.tif')
if ($sentinelFiles.Count -ne 18) {
    throw "Expected exactly 18 Sentinel-2 GeoTIFFs in $SentinelSource, found $($sentinelFiles.Count)."
}
$sentinelDestination = Join-Path $packageData 'raw\sentinel2\dixie_fire_2021\gee'
New-Item -ItemType Directory -Path $sentinelDestination -Force | Out-Null
foreach ($file in $sentinelFiles) {
    Copy-Item -LiteralPath $file.FullName -Destination $sentinelDestination -Force
}

$seed = (Resolve-Path -LiteralPath $SeedPath).Path
$databaseDestination = Join-Path $destination 'database'
New-Item -ItemType Directory -Path $databaseDestination -Force | Out-Null
Copy-Item -LiteralPath $seed -Destination (Join-Path $databaseDestination 'dixie_fire_2021_database_seed.sql') -Force

if ($IncludeLocalEnv) {
    $localEnv = Join-Path $repo '.env'
    if (-not (Test-Path -LiteralPath $localEnv -PathType Leaf)) {
        throw "IncludeLocalEnv was specified but no local .env exists at $localEnv"
    }
    $configDestination = Join-Path $destination 'local-config'
    New-Item -ItemType Directory -Path $configDestination -Force | Out-Null
    Copy-Item -LiteralPath $localEnv -Destination (Join-Path $configDestination '.env') -Force
}

$inventory = Get-ChildItem -LiteralPath $destination -Recurse -File | ForEach-Object {
    [pscustomobject]@{
        path = [System.IO.Path]::GetRelativePath($destination, $_.FullName).Replace('\', '/')
        bytes = $_.Length
    }
}
$summary = [ordered]@{
    package_version = '1.0'
    event_id = 'dixie_fire_2021'
    created_at = (Get-Date).ToString('o')
    sentinel_geotiff_count = $sentinelFiles.Count
    file_count = @($inventory).Count
    total_bytes = ($inventory | Measure-Object -Property bytes -Sum).Sum
    includes_local_env = [bool]$IncludeLocalEnv
    files = @($inventory)
}
$summary | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $destination 'handoff-manifest.json') -Encoding UTF8

Write-Host "USB package ready: $destination"
Write-Host "Files: $($summary.file_count); bytes: $($summary.total_bytes); Sentinel GeoTIFFs: $($summary.sentinel_geotiff_count)"

