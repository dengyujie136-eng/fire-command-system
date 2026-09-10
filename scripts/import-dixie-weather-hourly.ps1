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
$csvPath = Join-Path $repoRoot 'data\processed\weather\dixie_fire_2021_nasa_power_hourly.csv'

$psqlCommand = Get-Command psql -ErrorAction SilentlyContinue
if (-not $psqlCommand) { throw 'psql was not found. Activate the environment with the PostgreSQL client.' }
if (-not (Test-Path -LiteralPath $csvPath)) { throw "Normalized hourly CSV not found: $csvPath" }

$env:PGPASSWORD = $DbPassword
$psqlArgs = @('-h', $DbHost, '-p', $DbPort, '-U', $DbUser, '-d', $DbName, '-v', 'ON_ERROR_STOP=1')

Write-Host '[1/3] Creating hourly weather tables'
& $psqlCommand.Source @psqlArgs -f (Join-Path $sqlDir '006_weather_hourly_schema.sql')
if ($LASTEXITCODE -ne 0) { throw 'Hourly weather schema creation failed.' }

Write-Host '[2/3] Loading normalized hourly CSV into staging'
& $psqlCommand.Source @psqlArgs -c 'TRUNCATE staging.nasa_power_hourly;'
if ($LASTEXITCODE -ne 0) { throw 'Hourly weather staging cleanup failed.' }
$localPath = $csvPath.Replace('\', '/').Replace("'", "''")
$copySql = "\copy staging.nasa_power_hourly (timestamp_utc, observed_on, longitude, latitude, elevation_m, temperature_c, relative_humidity_percent, wind_speed_m_s, wind_direction_deg, wind_u_m_s, wind_v_m_s, precipitation_mm, solar_radiation_mj_m2_h, is_interpolated, source_dataset) FROM '$localPath' WITH (FORMAT csv, HEADER true);"
& $psqlCommand.Source @psqlArgs -c $copySql
if ($LASTEXITCODE -ne 0) { throw 'Hourly weather CSV load failed.' }

Write-Host '[3/3] Writing Dixie Fire hourly weather observations and manifest'
& $psqlCommand.Source @psqlArgs -f (Join-Path $sqlDir '007_load_dixie_weather_hourly.sql')
if ($LASTEXITCODE -ne 0) { throw 'Dixie Fire hourly weather final load failed.' }

Write-Host 'Hourly weather load completed.'
