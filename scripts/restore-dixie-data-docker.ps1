param(
    [Parameter(Mandatory = $true)]
    [string]$SeedPath,
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$DbName = $(if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { 'xinghuo' }),
    [string]$DbUser = $(if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { 'xinghuo' }),
    [string]$DbPassword = $(if ($env:POSTGRES_PASSWORD) { $env:POSTGRES_PASSWORD } else { 'xinghuo_dev' })
)

$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path $RepoRoot)
$SeedPath = (Resolve-Path $SeedPath).Path
if (-not (Test-Path $SeedPath -PathType Leaf)) { throw "Seed file not found: $SeedPath" }

Write-Host '[1/3] Starting the backend and PostGIS container'
docker compose up -d fire-agent-api
if ($LASTEXITCODE -ne 0) { throw 'PostGIS or fire-agent-api failed to start.' }

Write-Host '[2/4] Creating the甲侧 data tables'
$schemaFiles = @('001_fire_data_schema.sql', '003_weather_schema.sql', '006_weather_hourly_schema.sql')
foreach ($schemaFile in $schemaFiles) {
    $schemaPath = Join-Path $RepoRoot "data\sql\$schemaFile"
    if (-not (Test-Path $schemaPath -PathType Leaf)) { throw "Schema file not found: $schemaPath" }
    Get-Content -LiteralPath $schemaPath -Raw -Encoding UTF8 |
        docker compose exec -T postgis psql -U $DbUser -d $DbName -v ON_ERROR_STOP=1 -f -
    if ($LASTEXITCODE -ne 0) { throw "Schema creation failed: $schemaFile" }
}

Write-Host '[3/4] Restoring only dixie_fire_2021 data'
$env:PGPASSWORD = $DbPassword
@"
BEGIN;
DELETE FROM public.fire_hotspots WHERE event_id = 'dixie_fire_2021';
DELETE FROM public.fire_hotspot_clusters WHERE event_id = 'dixie_fire_2021';
DELETE FROM public.firms_hotspot_observations WHERE event_id = 'dixie_fire_2021';
DELETE FROM public.burned_areas WHERE event_id = 'dixie_fire_2021';
DELETE FROM public.weather_hourly_observations WHERE event_id = 'dixie_fire_2021';
DELETE FROM public.weather_observations WHERE event_id = 'dixie_fire_2021';
DELETE FROM public.fire_data_manifests WHERE event_id = 'dixie_fire_2021';
COMMIT;
"@ | docker compose exec -T postgis psql -U $DbUser -d $DbName -v ON_ERROR_STOP=1 -f -
if ($LASTEXITCODE -ne 0) { throw 'Existing Dixie Fire data cleanup failed.' }
Get-Content -LiteralPath $SeedPath -Raw -Encoding UTF8 |
    docker compose exec -T postgis psql -U $DbUser -d $DbName -v ON_ERROR_STOP=1 -f -
if ($LASTEXITCODE -ne 0) { throw 'Dixie Fire database seed restore failed.' }

Write-Host '[4/4] Verifying restored counts'
$sql = @"
SELECT json_build_object(
  'event', (SELECT count(*) FROM fire_events WHERE event_id = 'dixie_fire_2021'),
  'firms_raw', (SELECT count(*) FROM firms_hotspot_observations WHERE event_id = 'dixie_fire_2021'),
  'hotspots', (SELECT count(*) FROM fire_hotspots WHERE event_id = 'dixie_fire_2021'),
  'clusters', (SELECT count(*) FROM fire_hotspot_clusters WHERE event_id = 'dixie_fire_2021'),
  'burned_area', (SELECT count(*) FROM burned_areas WHERE event_id = 'dixie_fire_2021'),
  'weather_daily', (SELECT count(*) FROM weather_observations WHERE event_id = 'dixie_fire_2021'),
  'weather_hourly', (SELECT count(*) FROM weather_hourly_observations WHERE event_id = 'dixie_fire_2021')
);
"@
docker compose exec -T postgis psql -U $DbUser -d $DbName -At -c $sql
if ($LASTEXITCODE -ne 0) { throw 'Dixie Fire database verification failed.' }
Write-Host 'Dixie Fire database restore completed without touching other events.'
