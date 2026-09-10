param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
)

$ErrorActionPreference = 'Stop'
$firmsDir = Join-Path $RepoRoot 'data\raw\firms'
$burnedDir = Join-Path $RepoRoot 'data\raw\burned_area\dixie_fire_2021_mtbs_burn_area'
$burnedZip = Join-Path $RepoRoot 'data\raw\burned_area\dixie_fire_2021_mtbs_burn_area.zip'
$weatherRaw = Join-Path $RepoRoot 'data\raw\weather\dixie_fire_2021_nasa_power_daily.json'
$weatherProcessed = Join-Path $RepoRoot 'data\processed\weather\dixie_fire_2021_nasa_power_daily.csv'
$weatherHourlyRaw = Join-Path $RepoRoot 'data\raw\weather\dixie_fire_2021_nasa_power_hourly.json'
$weatherHourlyProcessed = Join-Path $RepoRoot 'data\processed\weather\dixie_fire_2021_nasa_power_hourly.csv'
$weatherHourlyMetadata = Join-Path $RepoRoot 'data\processed\weather\dixie_fire_2021_nasa_power_hourly_metadata.json'
$demProcessed = Join-Path $RepoRoot 'data\processed\dem\dixie_fire_2021_copernicus_dem_30m_utm10.tif'
$slopeProcessed = Join-Path $RepoRoot 'data\processed\dem\dixie_fire_2021_slope_deg_30m_utm10.tif'
$aspectProcessed = Join-Path $RepoRoot 'data\processed\dem\dixie_fire_2021_aspect_deg_30m_utm10.tif'
$worldCoverProcessed = Join-Path $RepoRoot 'data\processed\fuel\dixie_fire_2021_worldcover_30m_utm10.tif'
$fuelProcessed = Join-Path $RepoRoot 'data\processed\fuel\dixie_fire_2021_fuel_class_30m_utm10.tif'
$rasterSources = Join-Path $RepoRoot 'data\manifests\dixie_fire_2021_raster_sources.json'
$fuelMapping = Join-Path $RepoRoot 'data\manifests\dixie_fire_2021_worldcover_fuel_mapping.json'
$forefireInputManifest = Join-Path $RepoRoot 'data\processed\forefire_input\dixie_fire_2021_forefire_input_manifest.json'
$output = Join-Path $RepoRoot 'data\manifests\dixie_fire_2021.json'

function Convert-ToRelativePath([string]$Path) {
    $root = ([IO.Path]::GetFullPath($RepoRoot)).TrimEnd('\') + '\'
    $fullPath = [IO.Path]::GetFullPath($Path)
    $relative = $fullPath.Substring($root.Length)
    return $relative.Replace('\', '/')
}

function New-FileRecord([IO.FileInfo]$File) {
    $hash = (Get-FileHash -LiteralPath $File.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    return [ordered]@{
        path = Convert-ToRelativePath $File.FullName
        size_bytes = $File.Length
        sha256 = $hash
    }
}

if (-not (Test-Path $firmsDir)) { throw "FIRMS directory not found: $firmsDir" }
if (-not (Test-Path $burnedZip)) { throw "MTBS ZIP not found: $burnedZip" }
if (-not (Test-Path $weatherRaw)) { throw "NASA POWER raw JSON not found: $weatherRaw" }
if (-not (Test-Path $weatherHourlyRaw)) { throw "NASA POWER hourly raw JSON not found: $weatherHourlyRaw" }
if (-not (Test-Path $weatherHourlyProcessed)) { throw "NASA POWER hourly CSV not found: $weatherHourlyProcessed" }
if (-not (Test-Path $weatherHourlyMetadata)) { throw "NASA POWER hourly metadata not found: $weatherHourlyMetadata" }
if (-not (Test-Path $demProcessed)) { throw "Processed DEM not found: $demProcessed" }
if (-not (Test-Path $slopeProcessed)) { throw "Processed slope not found: $slopeProcessed" }
if (-not (Test-Path $aspectProcessed)) { throw "Processed aspect not found: $aspectProcessed" }
if (-not (Test-Path $worldCoverProcessed)) { throw "Processed WorldCover not found: $worldCoverProcessed" }
if (-not (Test-Path $fuelProcessed)) { throw "Processed fuel class raster not found: $fuelProcessed" }
if (-not (Test-Path $rasterSources)) { throw "Raster source catalog not found: $rasterSources" }
if (-not (Test-Path $fuelMapping)) { throw "Fuel mapping not found: $fuelMapping" }
if (-not (Test-Path $forefireInputManifest)) { throw "ForeFire input manifest not found: $forefireInputManifest" }

$firmsFiles = @(Get-ChildItem -LiteralPath $firmsDir -File -Filter '*.csv' | Sort-Object Name)
$burnedFiles = @()
$burnedFiles += Get-Item -LiteralPath $burnedZip
if (Test-Path $burnedDir) {
    $burnedFiles += @(Get-ChildItem -LiteralPath $burnedDir -Recurse -File | Sort-Object FullName)
}
$weatherFiles = @(Get-Item -LiteralPath $weatherRaw)
if (Test-Path $weatherProcessed) {
    $weatherFiles += Get-Item -LiteralPath $weatherProcessed
}
$weatherHourlyFiles = @(
    Get-Item -LiteralPath $weatherHourlyRaw
    Get-Item -LiteralPath $weatherHourlyProcessed
    Get-Item -LiteralPath $weatherHourlyMetadata
)
$rasterFiles = @(
    Get-Item -LiteralPath $demProcessed
    Get-Item -LiteralPath $slopeProcessed
    Get-Item -LiteralPath $aspectProcessed
    Get-Item -LiteralPath $worldCoverProcessed
    Get-Item -LiteralPath $fuelProcessed
    Get-Item -LiteralPath $rasterSources
    Get-Item -LiteralPath $fuelMapping
)

$manifest = [ordered]@{
    schema_version = 'fire.dataset.manifest.v0.1'
    event_id = 'dixie_fire_2021'
    event_name = 'Dixie Fire'
    generated_at = (Get-Date).ToUniversalTime().ToString('o')
    spatial_extent = [ordered]@{ west = -122.5; south = 39.0; east = -119.0; north = 42.0; crs = 'EPSG:4326' }
    temporal_extent = @('2021-07-13', '2021-10-25')
    datasets = @(
        [ordered]@{
            dataset_id = 'dixie_fire_2021_firms_viirs_snpp_sp'
            name = 'Dixie Fire VIIRS S-NPP historical hotspot observations'
            source_url = 'https://firms.modaps.eosdis.nasa.gov/'
            license = 'NASA Earthdata/FIRMS'
            source_crs = 'EPSG:4326'
            target_crs = 'EPSG:4326'
            temporal_extent = @('2021-07-13', '2021-10-25')
            processing_steps = @('CSV header validation', 'UTC time normalization', 'point geometry creation', 'MTBS perimeter spatial filtering')
            files = @($firmsFiles | ForEach-Object { New-FileRecord $_ })
        }
        [ordered]@{
            dataset_id = 'dixie_fire_2021_mtbs_burn_area'
            name = 'Dixie Fire MTBS burned area boundary'
            source_url = 'https://www.mtbs.gov/'
            license = 'USGS/USDA Forest Service MTBS'
            source_crs = 'EPSG:5070'
            target_crs = 'EPSG:4326'
            temporal_extent = @('2020-07-08', '2022-07-14')
            processing_steps = @('Shapefile bundle validation', 'Albers to WGS84 transformation', 'ST_MakeValid geometry repair', 'MultiPolygon validation')
            files = @($burnedFiles | ForEach-Object { New-FileRecord $_ })
        }
        [ordered]@{
            dataset_id = 'dixie_fire_2021_nasa_power_daily'
            name = 'Dixie Fire NASA POWER daily meteorological baseline'
            source_url = 'https://power.larc.nasa.gov/'
            license = 'NASA POWER data access terms'
            source_crs = 'EPSG:4326'
            target_crs = 'EPSG:4326'
            temporal_extent = @('2021-07-13', '2021-10-25')
            processing_steps = @('NASA POWER daily point query', 'UTC time standard', 'JSON to normalized CSV', 'point geometry creation')
            files = @($weatherFiles | ForEach-Object { New-FileRecord $_ })
        }
        [ordered]@{
            dataset_id = 'dixie_fire_2021_nasa_power_hourly'
            name = 'Dixie Fire NASA POWER hourly meteorological input'
            source_url = 'https://power.larc.nasa.gov/'
            license = 'NASA POWER data access terms'
            source_crs = 'EPSG:4326'
            target_crs = 'EPSG:4326'
            temporal_extent = @('2021-07-13T00:00:00Z', '2021-10-25T23:00:00Z')
            processing_steps = @('NASA POWER hourly point query', 'UTC time standard', 'JSON to normalized CSV', 'wind component derivation', 'no interpolation')
            files = @($weatherHourlyFiles | ForEach-Object { New-FileRecord $_ })
        }
        [ordered]@{
            dataset_id = 'dixie_fire_2021_copernicus_dem_glo30'
            name = 'Dixie Fire Copernicus DEM GLO-30 AOI product'
            source_url = 'https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-digital-elevation-model'
            license = 'Copernicus DEM license'
            source_crs = 'EPSG:4326'
            target_crs = 'EPSG:32610'
            temporal_extent = @('2021-07-13', '2021-10-25')
            processing_steps = @('AOI boundary from MTBS perimeter plus 15 km buffer', 'four COG tiles mosaicked', 'reprojected to UTM zone 10N', 'resampled to 30 m')
            files = @($rasterFiles | Where-Object { $_.Name -like '*dem*' -or $_.Name -like '*slope*' -or $_.Name -like '*aspect*' -or $_.Name -like '*raster_sources*' } | ForEach-Object { New-FileRecord $_ })
        }
        [ordered]@{
            dataset_id = 'dixie_fire_2021_esa_worldcover_2021'
            name = 'Dixie Fire ESA WorldCover 2021 AOI product'
            source_url = 'https://esa-worldcover.org/en/data-access'
            license = 'ESA WorldCover license'
            source_crs = 'EPSG:4326'
            target_crs = 'EPSG:32610'
            temporal_extent = @('2021-01-01', '2021-12-31')
            processing_steps = @('AOI boundary from MTBS perimeter plus 15 km buffer', '10 m source product read from COG', 'reprojected to UTM zone 10N', 'nearest-neighbour resampled to 30 m', 'mapped to simplified fuel classes')
            files = @($rasterFiles | Where-Object { $_.Name -like '*worldcover*' -or $_.Name -like '*fuel_class*' -or $_.Name -like '*fuel_mapping*' -or $_.Name -like '*raster_sources*' } | ForEach-Object { New-FileRecord $_ })
        }
        [ordered]@{
            dataset_id = 'dixie_fire_2021_forefire_input_manifest'
            name = 'Dixie Fire ForeFire input preparation manifest'
            source_url = 'https://github.com/forefireAPI/firefront'
            license = 'Project input manifest; source dataset licenses are recorded per input dataset'
            source_crs = 'EPSG:4326'
            target_crs = 'EPSG:32610'
            temporal_extent = @('2021-07-14T09:11:00Z', '2021-10-25T23:00:00Z')
            processing_steps = @('deterministic ignition candidate selection', '30 m raster input inventory', 'NASA POWER hourly weather inventory', 'SHA-256 file checksums')
            files = @((Get-Item -LiteralPath $forefireInputManifest) | ForEach-Object { New-FileRecord $_ })
        }
    )
}

New-Item -ItemType Directory -Force -Path (Split-Path $output) | Out-Null
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($output, ($manifest | ConvertTo-Json -Depth 10), $utf8NoBom)
Write-Host "Manifest written: $output"
