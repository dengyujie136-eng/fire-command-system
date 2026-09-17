param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
)

$ErrorActionPreference = 'Stop'
$aoi = @{
    west = -121.720069
    south = 39.727100
    east = -120.009180
    north = 40.918238
}
$targetCrs = 'EPSG:32610'
$demDir = Join-Path $RepoRoot 'data\processed\dem'
$fuelDir = Join-Path $RepoRoot 'data\processed\fuel'
$sourceDir = Join-Path $RepoRoot 'data\manifests'
$demOutput = Join-Path $demDir 'dixie_fire_2021_copernicus_dem_30m_utm10.tif'
$slopeOutput = Join-Path $demDir 'dixie_fire_2021_slope_deg_30m_utm10.tif'
$aspectOutput = Join-Path $demDir 'dixie_fire_2021_aspect_deg_30m_utm10.tif'
$worldCoverOutput = Join-Path $fuelDir 'dixie_fire_2021_worldcover_30m_utm10.tif'
$fuelOutput = Join-Path $fuelDir 'dixie_fire_2021_fuel_class_30m_utm10.tif'
$sourceOutput = Join-Path $sourceDir 'dixie_fire_2021_raster_sources.json'

$gdalWarp = Get-Command gdalwarp -ErrorAction SilentlyContinue
if (-not $gdalWarp) { throw 'gdalwarp was not found. Activate the Conda GIS environment first.' }

New-Item -ItemType Directory -Force -Path $demDir, $fuelDir, $sourceDir | Out-Null

function Get-SignedUrl([string]$collection, [string]$href) {
    $encodedHref = [Uri]::EscapeDataString($href)
    $signed = Invoke-RestMethod -Uri "https://planetarycomputer.microsoft.com/api/sas/v1/sign?href=$encodedHref" -TimeoutSec 60
    return $signed.href
}

$worldCoverHref = 'https://ai4edataeuwest.blob.core.windows.net/esa-worldcover/v200/2021/map/ESA_WorldCover_10m_2021_v200_N39W123_Map.tif'
$demHrefs = @(
    'https://elevationeuwest.blob.core.windows.net/copernicus-dem/COP30_hh/Copernicus_DSM_COG_10_N40_00_W122_00_DEM.tif',
    'https://elevationeuwest.blob.core.windows.net/copernicus-dem/COP30_hh/Copernicus_DSM_COG_10_N40_00_W121_00_DEM.tif',
    'https://elevationeuwest.blob.core.windows.net/copernicus-dem/COP30_hh/Copernicus_DSM_COG_10_N39_00_W122_00_DEM.tif',
    'https://elevationeuwest.blob.core.windows.net/copernicus-dem/COP30_hh/Copernicus_DSM_COG_10_N39_00_W121_00_DEM.tif'
)

$worldCoverUrl = Get-SignedUrl 'esa-worldcover' $worldCoverHref
$demUrls = @($demHrefs | ForEach-Object { Get-SignedUrl 'cop-dem-glo-30' $_ })
$worldCoverSource = "/vsicurl/$worldCoverUrl"
$demSources = @($demUrls | ForEach-Object { "/vsicurl/$_" })

if (-not (Test-Path $worldCoverOutput)) {
    Write-Host '[1/3] Clipping and reprojecting ESA WorldCover 2021 to the Dixie AOI'
    $worldCoverArgs = @(
        '-overwrite', '-multi', '-wo', 'NUM_THREADS=ALL_CPUS', '-wm', '1024',
        '-te', $aoi.west, $aoi.south, $aoi.east, $aoi.north, '-te_srs', 'EPSG:4326',
        '-t_srs', $targetCrs, '-tr', '30', '30', '-tap', '-r', 'near',
        '-srcnodata', '0', '-dstnodata', '0', '-of', 'GTiff',
        '-co', 'TILED=YES', '-co', 'COMPRESS=DEFLATE', '-co', 'PREDICTOR=2', '-co', 'BIGTIFF=IF_SAFER',
        $worldCoverSource, $worldCoverOutput
    )
    & $gdalWarp.Source @worldCoverArgs
    if ($LASTEXITCODE -ne 0) { throw 'WorldCover processing failed.' }
} else {
    Write-Host '[1/3] WorldCover output already exists; keeping it'
}

if (-not (Test-Path $demOutput)) {
    Write-Host '[2/3] Mosaicking, clipping and reprojecting Copernicus DEM to the Dixie AOI'
    $demArgs = @(
        '-overwrite', '-multi', '-wo', 'NUM_THREADS=ALL_CPUS', '-wm', '1024',
        '-te', $aoi.west, $aoi.south, $aoi.east, $aoi.north, '-te_srs', 'EPSG:4326',
        '-t_srs', $targetCrs, '-tr', '30', '30', '-tap', '-r', 'bilinear',
        '-dstnodata', '-9999', '-of', 'GTiff',
        '-co', 'TILED=YES', '-co', 'COMPRESS=DEFLATE', '-co', 'PREDICTOR=2', '-co', 'BIGTIFF=IF_SAFER'
    ) + $demSources + @($demOutput)
    & $gdalWarp.Source @demArgs
    if ($LASTEXITCODE -ne 0) { throw 'Copernicus DEM processing failed.' }
} else {
    Write-Host '[2/3] DEM output already exists; keeping it'
}

$gdalDem = Get-Command gdaldem -ErrorAction SilentlyContinue
if (-not $gdalDem) { throw 'gdaldem was not found. Activate the Conda GIS environment first.' }
if (-not (Test-Path $slopeOutput)) {
    Write-Host '[2/5] Deriving slope raster from DEM'
    & $gdalDem.Source slope $demOutput $slopeOutput -compute_edges -of GTiff -co TILED=YES -co COMPRESS=DEFLATE -co BIGTIFF=IF_SAFER
    if ($LASTEXITCODE -ne 0) { throw 'Slope derivation failed.' }
}
if (-not (Test-Path $aspectOutput)) {
    Write-Host '[2/5] Deriving aspect raster from DEM'
    & $gdalDem.Source aspect $demOutput $aspectOutput -compute_edges -of GTiff -co TILED=YES -co COMPRESS=DEFLATE -co BIGTIFF=IF_SAFER
    if ($LASTEXITCODE -ne 0) { throw 'Aspect derivation failed.' }
}

$gdalCalc = Get-Command gdal_calc.py -ErrorAction SilentlyContinue
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $gdalCalc -or -not $python) { throw 'Python and gdal_calc.py are required for fuel-class derivation.' }
if (-not (Test-Path $fuelOutput)) {
    Write-Host '[2/5] Mapping WorldCover classes to simplified fuel classes'
    $fuelCalc = '((A==10)*1 + (A==20)*2 + (A==30)*3 + (A==40)*4 + (A==60)*4 + (A==90)*5 + (A==95)*6 + (A==100)*4)'
    $fuelArgs = @(
        $gdalCalc.Source, '-A', $worldCoverOutput, "--outfile=$fuelOutput", "--calc=$fuelCalc",
        '--type=Byte', '--NoDataValue=0', '--overwrite', '--co=TILED=YES', '--co=COMPRESS=DEFLATE', '--co=BIGTIFF=IF_SAFER'
    )
    & $python.Source @fuelArgs
    if ($LASTEXITCODE -ne 0) { throw 'Fuel-class derivation failed.' }
}

$sourceCatalog = [ordered]@{
    schema_version = 'fire.raster.sources.v0.1'
    event_id = 'dixie_fire_2021'
    aoi = [ordered]@{
        west = $aoi.west
        south = $aoi.south
        east = $aoi.east
        north = $aoi.north
        crs = 'EPSG:4326'
        buffer_m = 15000
    }
    processing_crs = $targetCrs
    datasets = @(
        [ordered]@{
            dataset_id = 'dixie_fire_2021_esa_worldcover_2021'
            source_url = $worldCoverHref
            stac_collection = 'esa-worldcover'
            source_resolution_m = 10
            output_resolution_m = 30
            output_path = 'data/processed/fuel/dixie_fire_2021_worldcover_30m_utm10.tif'
            resampling = 'nearest-neighbour'
            use = 'land-cover display and simplified fuel classification'
        }
        [ordered]@{
            dataset_id = 'dixie_fire_2021_copernicus_dem_glo30'
            source_url = 'https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-digital-elevation-model'
            stac_collection = 'cop-dem-glo-30'
            source_resolution_m = 30
            output_resolution_m = 30
            source_tiles = $demHrefs
            output_path = 'data/processed/dem/dixie_fire_2021_copernicus_dem_30m_utm10.tif'
            resampling = 'bilinear'
            use = 'terrain, slope and aspect inputs for fire spread'
        }
    )
}
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($sourceOutput, ($sourceCatalog | ConvertTo-Json -Depth 10), $utf8NoBom)

Write-Host '[3/5] Raster source catalog written'
Write-Host "WorldCover: $worldCoverOutput"
Write-Host "DEM: $demOutput"
Write-Host "Fuel classes: $fuelOutput"
Write-Host "Slope: $slopeOutput"
Write-Host "Aspect: $aspectOutput"
