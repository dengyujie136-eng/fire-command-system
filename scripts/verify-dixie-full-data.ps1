[CmdletBinding()]
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath $RepoRoot).Path

$requiredFiles = @(
    'data\raw\firms\dixie_fire_2021_20210713.csv',
    'data\raw\burned_area\dixie_fire_2021_mtbs_burn_area.zip',
    'data\processed\dem\dixie_fire_2021_copernicus_dem_30m_utm10.tif',
    'data\processed\dem\dixie_fire_2021_slope_deg_30m_utm10.tif',
    'data\processed\fuel\dixie_fire_2021_fuel_class_30m_utm10.tif',
    'data\processed\weather\dixie_fire_2021_nasa_power_hourly.csv',
    'data\local\database\dixie_fire_2021_database_seed.sql'
)

$missing = @()
foreach ($relativePath in $requiredFiles) {
    $absolutePath = Join-Path $repo $relativePath
    if (-not (Test-Path -LiteralPath $absolutePath -PathType Leaf)) {
        $missing += $relativePath
    }
}

$sentinelDirectory = Join-Path $repo 'data\raw\sentinel2\dixie_fire_2021\gee'
$sentinelFiles = if (Test-Path -LiteralPath $sentinelDirectory -PathType Container) {
    @(Get-ChildItem -LiteralPath $sentinelDirectory -File -Filter '*.tif')
} else {
    @()
}
$badSentinelFiles = if (Test-Path -LiteralPath $sentinelDirectory -PathType Container) {
    @(Get-ChildItem -LiteralPath $sentinelDirectory -File | Where-Object { $_.Extension -ne '.tif' })
} else {
    @()
}

$stageCounts = [ordered]@{
    pre = @($sentinelFiles | Where-Object Name -Match '_pre_').Count
    during = @($sentinelFiles | Where-Object Name -Match '_during_').Count
    post = @($sentinelFiles | Where-Object Name -Match '_post_').Count
}

$result = [ordered]@{
    status = if ($missing.Count -eq 0 -and $sentinelFiles.Count -eq 18 -and $badSentinelFiles.Count -eq 0 -and $stageCounts.pre -eq 6 -and $stageCounts.during -eq 6 -and $stageCounts.post -eq 6) { 'PASS' } else { 'FAIL' }
    repo_root = $repo
    missing_required_files = $missing
    sentinel_geotiff_count = $sentinelFiles.Count
    sentinel_stage_counts = $stageCounts
    unexpected_sentinel_files = @($badSentinelFiles.Name)
    sentinel_total_bytes = ($sentinelFiles | Measure-Object Length -Sum).Sum
}

$result | ConvertTo-Json -Depth 4
if ($result.status -ne 'PASS') {
    throw 'Dixie Fire full-data verification failed.'
}

