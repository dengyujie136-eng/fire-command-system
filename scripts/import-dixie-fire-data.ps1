param(
    [string]$DbHost = $(if ($env:POSTGRES_HOST) { $env:POSTGRES_HOST } else { 'localhost' }),
    [int]$DbPort = $(if ($env:POSTGRES_PORT) { [int]$env:POSTGRES_PORT } else { 5432 }),
    [string]$DbName = $(if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { 'xinghuo' }),
    [string]$DbUser = $(if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { 'xinghuo' }),
    [string]$DbPassword = $(if ($env:POSTGRES_PASSWORD) { $env:POSTGRES_PASSWORD } else { 'xinghuo_dev' })
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$sqlDir = Join-Path $repoRoot 'data\sql'
$firmsDir = Join-Path $repoRoot 'data\raw\firms'
$burnedDir = Join-Path $repoRoot 'data\raw\burned_area\dixie_fire_2021_mtbs_burn_area'

$psqlCommand = Get-Command psql -ErrorAction SilentlyContinue
$ogrCommand = Get-Command ogr2ogr -ErrorAction SilentlyContinue
if (-not $psqlCommand) { throw 'psql was not found. Activate a Conda environment with the PostgreSQL client.' }
if (-not $ogrCommand) { throw 'ogr2ogr was not found. Activate a Conda environment with GDAL.' }

$shp = Get-ChildItem -LiteralPath $burnedDir -Recurse -Filter '*_burn_area.shp' | Select-Object -First 1
if (-not $shp) { throw "MTBS burn_area Shapefile was not found: $burnedDir" }

$env:PGPASSWORD = $DbPassword
$connection = "host=$DbHost port=$DbPort dbname=$DbName user=$DbUser"
$psqlArgs = @('-h', $DbHost, '-p', $DbPort, '-U', $DbUser, '-d', $DbName, '-v', 'ON_ERROR_STOP=1')

Write-Host '[1/4] Creating fire data tables'
& $psqlCommand.Source @psqlArgs -f (Join-Path $sqlDir '001_fire_data_schema.sql')
if ($LASTEXITCODE -ne 0) { throw 'Database schema creation failed.' }

Write-Host '[2/4] Loading MTBS perimeter into staging'
& $ogrCommand.Source -f PostgreSQL "PG:$connection" $shp.FullName `
    -nln 'staging.mtbs_burn_area' -nlt PROMOTE_TO_MULTI -t_srs EPSG:4326 `
    -lco GEOMETRY_NAME=geom -lco FID=ogc_fid -overwrite
if ($LASTEXITCODE -ne 0) { throw 'MTBS Shapefile load failed.' }

Write-Host '[3/4] Loading all FIRMS CSV files into staging'
& $psqlCommand.Source @psqlArgs -c 'TRUNCATE staging.firms_raw;'
if ($LASTEXITCODE -ne 0) { throw 'FIRMS staging cleanup failed.' }

$csvFiles = Get-ChildItem -LiteralPath $firmsDir -File -Filter '*.csv' | Sort-Object Name
if ($csvFiles.Count -eq 0) { throw "No FIRMS CSV files found: $firmsDir" }
foreach ($csv in $csvFiles) {
    $localPath = $csv.FullName.Replace('\', '/').Replace("'", "''")
    $copySql = "\copy staging.firms_raw (latitude, longitude, bright_ti4, scan, track, acq_date, acq_time, satellite, instrument, confidence, version, bright_ti5, frp, daynight, type) FROM '$localPath' WITH (FORMAT csv, HEADER true); UPDATE staging.firms_raw SET source_file = 'data/raw/firms/$($csv.Name)' WHERE source_file IS NULL;"
    & $psqlCommand.Source @psqlArgs -c $copySql
    if ($LASTEXITCODE -ne 0) { throw "FIRMS load failed: $($csv.Name)" }
    Write-Host "  loaded $($csv.Name)"
}

Write-Host '[4/4] Creating event, filtering hotspots, and loading final tables'
& $psqlCommand.Source @psqlArgs -f (Join-Path $sqlDir '002_load_dixie_fire.sql')
if ($LASTEXITCODE -ne 0) { throw 'Dixie Fire final load failed.' }

Write-Host 'Dixie Fire data load completed.'
