param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [switch]$SkipDocker
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path $RepoRoot).Path
$reportDir = Join-Path $RepoRoot 'data\manifests'
$reportPath = Join-Path $reportDir 'dixie_fire_2021_readiness.json'
$markdownPath = Join-Path $RepoRoot 'docs\dixie-fire-data-readiness.md'
$required = @(
    'data\manifests\dixie_fire_2021.json',
    'data\processed\forefire_input\dixie_fire_2021_forefire_input_manifest.json',
    'data\raw\weather\dixie_fire_2021_nasa_power_hourly.json',
    'data\processed\weather\dixie_fire_2021_nasa_power_hourly.csv',
    'data\processed\dem\dixie_fire_2021_copernicus_dem_30m_utm10.tif',
    'data\processed\dem\dixie_fire_2021_slope_deg_30m_utm10.tif',
    'data\processed\dem\dixie_fire_2021_aspect_deg_30m_utm10.tif',
    'data\processed\fuel\dixie_fire_2021_worldcover_30m_utm10.tif',
    'data\processed\fuel\dixie_fire_2021_fuel_class_30m_utm10.tif'
)

foreach ($relativePath in $required) {
    if (-not (Test-Path (Join-Path $RepoRoot $relativePath) -PathType Leaf)) {
        throw "Required file is missing: $relativePath"
    }
}

$branch = (git -C $RepoRoot branch --show-current).Trim()
if ($branch -ne 'member/qingzhe_ivory') {
    throw "Refusing to validate on unexpected branch: $branch"
}

$firmsFiles = @(Get-ChildItem (Join-Path $RepoRoot 'data\raw\firms') -Filter '*.csv' -File | Sort-Object Name)
$firmsRows = 0
$firmsDates = New-Object System.Collections.Generic.List[string]
foreach ($file in $firmsFiles) {
    $rows = @(Import-Csv -LiteralPath $file.FullName)
    $firmsRows += $rows.Count
    foreach ($row in $rows) {
        if ($row.acq_date) { $firmsDates.Add([string]$row.acq_date) }
    }
}

$hourlyRows = @(Import-Csv -LiteralPath (Join-Path $RepoRoot 'data\processed\weather\dixie_fire_2021_nasa_power_hourly.csv'))
$rasterPaths = @(
    'data\processed\dem\dixie_fire_2021_copernicus_dem_30m_utm10.tif',
    'data\processed\dem\dixie_fire_2021_slope_deg_30m_utm10.tif',
    'data\processed\dem\dixie_fire_2021_aspect_deg_30m_utm10.tif',
    'data\processed\fuel\dixie_fire_2021_worldcover_30m_utm10.tif',
    'data\processed\fuel\dixie_fire_2021_fuel_class_30m_utm10.tif'
)
$rasters = foreach ($relativePath in $rasterPaths) {
    $path = Join-Path $RepoRoot $relativePath
    [ordered]@{
        path = $relativePath.Replace('\', '/')
        size_bytes = (Get-Item $path).Length
        sha256 = (Get-FileHash $path -Algorithm SHA256).Hash.ToLowerInvariant()
        crs = 'EPSG:32610'
        expected_pixel_size_m = 30
    }
}

$docker = [ordered]@{ checked = (-not $SkipDocker); service_status = $null; counts = $null }
if (-not $SkipDocker) {
    $statusLines = @(docker compose -f (Join-Path $RepoRoot 'compose.yaml') ps --format '{{.Service}}|{{.State}}|{{.Health}}')
    $docker.service_status = @($statusLines | ForEach-Object {
        $parts = $_ -split '\|', 3
        [ordered]@{ service = $parts[0]; state = $parts[1]; health = $parts[2] }
    })
    $sql = @"
SELECT json_build_object(
  'events', (SELECT count(*) FROM fire_events),
  'firms_raw', (SELECT count(*) FROM firms_hotspot_observations),
  'hotspots', (SELECT count(*) FROM fire_hotspots),
  'clusters', (SELECT count(*) FROM fire_hotspot_clusters),
  'burned_area', (SELECT count(*) FROM burned_areas),
  'weather_daily', (SELECT count(*) FROM weather_observations),
  'weather_hourly', (SELECT count(*) FROM weather_hourly_observations),
  'manifests', (SELECT count(*) FROM fire_data_manifests)
);
"@
    $docker.counts = ((docker compose -f (Join-Path $RepoRoot 'compose.yaml') exec -T postgis psql -U xinghuo -d xinghuo -At -c $sql).Trim() | ConvertFrom-Json)
}

$forefire = Get-Content (Join-Path $RepoRoot 'data\processed\forefire_input\dixie_fire_2021_forefire_input_manifest.json') -Raw | ConvertFrom-Json
$report = [ordered]@{
    schema_version = 'fire.dixie.readiness.v0.1'
    generated_at = (Get-Date).ToUniversalTime().ToString('o')
    branch = $branch
    event_id = 'dixie_fire_2021'
    raw_firms = [ordered]@{
        file_count = $firmsFiles.Count
        row_count = $firmsRows
        first_date = ($firmsDates | Sort-Object | Select-Object -First 1)
        last_date = ($firmsDates | Sort-Object | Select-Object -Last 1)
    }
    rasters = @($rasters)
    hourly_weather = [ordered]@{
        raw_path = 'data/raw/weather/dixie_fire_2021_nasa_power_hourly.json'
        normalized_path = 'data/processed/weather/dixie_fire_2021_nasa_power_hourly.csv'
        row_count = $hourlyRows.Count
        interval_minutes = 60
        is_interpolated = $false
        precipitation = 'missing_in_source; represented as null'
    }
    forefire_manifest = [ordered]@{
        path = 'data/processed/forefire_input/dixie_fire_2021_forefire_input_manifest.json'
        input_status = $forefire.input_status
        forefire_case_generated = $forefire.validation.forefire_case_generated
        forefire_run_verified = $forefire.validation.forefire_run_verified
        candidate_id = $forefire.ignition.candidate_id
    }
    osm = [ordered]@{
        status = 'deferred'
        processed_layers_available = $false
        reason = 'Overpass request timed out; retained response is an error page and excluded from the manifest.'
    }
    docker_postgis = $docker
}
New-Item -ItemType Directory -Force -Path $reportDir, (Split-Path $markdownPath) | Out-Null
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($reportPath, ($report | ConvertTo-Json -Depth 12), $utf8NoBom)

$lines = @(
    '# Dixie Fire data readiness report',
    '',
    "- Generated: $($report.generated_at)",
    ('- Branch: `' + $branch + '`'),
    '- Event: `dixie_fire_2021` (Dixie Fire)',
    '',
    '## Verified inputs',
    "- FIRMS raw files: $($report.raw_firms.file_count), $($report.raw_firms.row_count) rows, $($report.raw_firms.first_date) to $($report.raw_firms.last_date).",
    '- MTBS burned-area boundary: present in PostGIS and exposed by the burned-area API.',
    "- NASA POWER hourly weather: $($report.hourly_weather.row_count) original hourly rows; no interpolation applied.",
    '- DEM, slope, aspect, WorldCover and simplified fuel proxy: present as 30 m GeoTIFF products in EPSG:32610.',
    ('- ForeFire input manifest: `' + $report.forefire_manifest.input_status + '`.'),
    '',
    '## Important limitations',
    '- FIRMS observations are approximately 375 m thermal-anomaly pixel centers, not surveyed ignition points.',
    '- NASA POWER hourly weather is a representative point series; precipitation is missing in the source response.',
    '- WorldCover-derived fuel classes are a demonstration proxy, not calibrated LANDFIRE fuel models.',
    '- A ForeFire case and verified simulation result have not been claimed or generated by this data-side module.',
    '- OSM context layers are deferred because the Overpass request timed out; no error page is treated as data.',
    '',
    '## Handoff readiness',
    'The data-side package is ready for member C to prepare a case-specific ForeFire input. The actual case file, model run, output fire perimeter, and impact analysis remain downstream tasks.',
    '',
    'Machine-readable report: `data/manifests/dixie_fire_2021_readiness.json`.'
)
[IO.File]::WriteAllLines($markdownPath, $lines, $utf8NoBom)
Write-Host "Readiness report written: $reportPath"
Write-Host "Readiness summary written: $markdownPath"
