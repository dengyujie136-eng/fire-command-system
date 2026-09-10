param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$ApiBaseUrl = 'http://localhost:8200'
)

$ErrorActionPreference = 'Stop'
$eventId = 'dixie_fire_2021'
$outputDir = Join-Path $RepoRoot 'data\processed\forefire_input'
$outputPath = Join-Path $outputDir 'dixie_fire_2021_forefire_input_manifest.json'

New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

function Get-RelativePath([string]$Path) {
    $root = ([IO.Path]::GetFullPath($RepoRoot)).TrimEnd('\') + '\'
    return ([IO.Path]::GetFullPath($Path).Substring($root.Length)).Replace('\', '/')
}

function New-FileRecord([string]$RelativePath, [string]$Role, [string]$Crs, [string]$Format) {
    $absolutePath = Join-Path $RepoRoot ($RelativePath.Replace('/', '\'))
    if (-not (Test-Path -LiteralPath $absolutePath -PathType Leaf)) {
        throw "Required ForeFire input is missing: $absolutePath"
    }
    $file = Get-Item -LiteralPath $absolutePath
    return [ordered]@{
        role = $Role
        path = (Get-RelativePath $absolutePath)
        container_path = "/app/" + (Get-RelativePath $absolutePath)
        format = $Format
        crs = $Crs
        size_bytes = $file.Length
        sha256 = (Get-FileHash -LiteralPath $absolutePath -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}

try {
    $event = Invoke-RestMethod -Uri "$ApiBaseUrl/api/data/events/$eventId" -TimeoutSec 20
    $hotspots = Invoke-RestMethod -Uri "$ApiBaseUrl/api/data/events/$eventId/hotspots?status=candidate&aggregate=false&limit=1" -TimeoutSec 20
} catch {
    throw "Fire Agent API is required to build the manifest: $($_.Exception.Message)"
}

if (-not $hotspots.items -or $hotspots.items.Count -lt 1) {
    throw "No candidate hotspot is available for $eventId"
}

$firstCandidate = @($hotspots.items)[0]
$ignition = [ordered]@{
    rule = 'earliest candidate hotspot returned by the ordered candidate API'
    candidate_id = $firstCandidate.candidate_id
    observed_at = $firstCandidate.observed_at
    longitude = [double]$firstCandidate.location.longitude
    latitude = [double]$firstCandidate.location.latitude
    crs = 'EPSG:4326'
    precision = 'candidate coordinate rounded to 6 decimal places'
    note = 'This is a satellite thermal-anomaly candidate, not a surveyed ignition location.'
}

$inputs = @(
    New-FileRecord 'data/processed/dem/dixie_fire_2021_copernicus_dem_30m_utm10.tif' 'terrain_elevation' 'EPSG:32610' 'GeoTIFF'
    New-FileRecord 'data/processed/dem/dixie_fire_2021_slope_deg_30m_utm10.tif' 'terrain_slope_degrees' 'EPSG:32610' 'GeoTIFF'
    New-FileRecord 'data/processed/dem/dixie_fire_2021_aspect_deg_30m_utm10.tif' 'terrain_aspect_degrees' 'EPSG:32610' 'GeoTIFF'
    New-FileRecord 'data/processed/fuel/dixie_fire_2021_worldcover_30m_utm10.tif' 'land_cover_worldcover' 'EPSG:32610' 'GeoTIFF'
    New-FileRecord 'data/processed/fuel/dixie_fire_2021_fuel_class_30m_utm10.tif' 'fuel_class_proxy' 'EPSG:32610' 'GeoTIFF'
    New-FileRecord 'data/processed/weather/dixie_fire_2021_nasa_power_hourly.csv' 'weather_hourly_observations' 'EPSG:4326' 'CSV'
)

$manifest = [ordered]@{
    schema_version = 'fire.forefire.input.manifest.v0.1'
    event_id = $eventId
    event_name = 'Dixie Fire'
    generated_at = (Get-Date).ToUniversalTime().ToString('o')
    input_status = 'ready_for_member_c_preparation'
    purpose = 'Input contract and reproducibility manifest for preparing a Dixie Fire ForeFire case.'
    ignition = $ignition
    spatial_reference = [ordered]@{
        exchange_crs = 'EPSG:4326'
        raster_processing_crs = 'EPSG:32610'
        raster_resolution_m = 30
        aoi = [ordered]@{
            west = -121.720069
            south = 39.727100
            east = -120.009180
            north = 40.918238
            buffer_m = 15000
        }
    }
    weather = [ordered]@{
        source = 'NASA_POWER_HOURLY'
        interval_minutes = 60
        is_interpolated = $false
        endpoint = "/api/data/events/$eventId/weather-hourly"
        raw_path = 'data/raw/weather/dixie_fire_2021_nasa_power_hourly.json'
        normalized_path = 'data/processed/weather/dixie_fire_2021_nasa_power_hourly.csv'
        time_standard = 'UTC'
        precipitation_status = 'missing_in_source'
        note = 'Hourly temperature, relative humidity, wind speed and wind direction are available; hourly precipitation is null in the NASA POWER response.'
    }
    inputs = $inputs
    required_transformations = @(
        'Read the GeoTIFFs in EPSG:32610 at 30 m resolution and crop to the selected simulation domain.',
        'Map fuel_class_proxy values to the ForeFire fuel table selected by member C.',
        'Convert hourly wind speed and direction to windU and windV if required by the ForeFire NetCDF adapter.',
        'Keep the original hourly observations and mark any future resampled values as is_interpolated=true.',
        'Use the ignition candidate timestamp as the historical replay start time unless member C documents another case start.'
    )
    validation = [ordered]@{
        event_api_verified = $true
        candidate_api_verified = $true
        selected_candidate = $firstCandidate.candidate_id
        burned_area_api = "/api/data/events/$eventId/burned-area?include_geometry=true"
        hourly_weather_api = "/api/data/events/$eventId/weather-hourly"
        forefire_case_generated = $false
        forefire_run_verified = $false
    }
    limitations = @(
        'FIRMS VIIRS coordinates represent approximately 375 m thermal-anomaly pixels, not surveyed ignition coordinates.',
        'WorldCover-derived fuel classes are a course-demo proxy and are not calibrated LANDFIRE fuel models.',
        'NASA POWER hourly data is a representative point series, not a spatially varying weather field.',
        'This manifest does not claim that a Dixie Fire ForeFire simulation has already been run.'
    )
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($outputPath, ($manifest | ConvertTo-Json -Depth 12), $utf8NoBom)
Write-Host "ForeFire input manifest written: $outputPath"
Write-Host "Ignition candidate: $($ignition.candidate_id)"
