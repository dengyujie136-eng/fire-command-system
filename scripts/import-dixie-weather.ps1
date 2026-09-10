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
$weatherDir = Join-Path $repoRoot 'data\raw\weather'
$processedDir = Join-Path $repoRoot 'data\processed\weather'
$rawPath = Join-Path $weatherDir 'dixie_fire_2021_nasa_power_daily.json'
$normalizedPath = Join-Path $processedDir 'dixie_fire_2021_nasa_power_daily.csv'

$psqlCommand = Get-Command psql -ErrorAction SilentlyContinue
if (-not $psqlCommand) { throw 'psql was not found. Activate the environment with the PostgreSQL client.' }

New-Item -ItemType Directory -Force -Path $weatherDir, $processedDir | Out-Null
$url = 'https://power.larc.nasa.gov/api/temporal/daily/point?parameters=T2M,T2M_MAX,T2M_MIN,RH2M,WS10M,WD10M,PRECTOTCORR,ALLSKY_SFC_SW_DWN&community=AG&longitude=-121.38241&latitude=39.87194&start=20210713&end=20211025&format=JSON&time-standard=UTC'
if (-not (Test-Path $rawPath)) {
    Write-Host '[1/5] Downloading NASA POWER daily JSON'
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $rawPath
} else {
    Write-Host '[1/5] Using existing NASA POWER raw JSON'
}

Write-Host '[2/5] Normalizing daily weather fields'
$json = Get-Content -LiteralPath $rawPath -Raw | ConvertFrom-Json
$parameters = $json.properties.parameter
$elevation = [double]$json.geometry.coordinates[2]
$dates = @($parameters.T2M.PSObject.Properties.Name | Sort-Object)
$rows = New-Object System.Collections.Generic.List[object]

function Get-NasaValue([object]$parameter, [string]$date) {
    $property = $parameter.PSObject.Properties[$date]
    if (-not $property) { return $null }
    $value = [double]$property.Value
    if ($value -le -900) { return $null }
    return $value
}

foreach ($date in $dates) {
    $rows.Add([PSCustomObject]@{
        observed_on = [datetime]::ParseExact($date, 'yyyyMMdd', $null).ToString('yyyy-MM-dd')
        longitude = -121.38241
        latitude = 39.87194
        elevation_m = $elevation
        temperature_c = Get-NasaValue $parameters.T2M $date
        temperature_max_c = Get-NasaValue $parameters.T2M_MAX $date
        temperature_min_c = Get-NasaValue $parameters.T2M_MIN $date
        relative_humidity_percent = Get-NasaValue $parameters.RH2M $date
        wind_speed_m_s = Get-NasaValue $parameters.WS10M $date
        wind_direction_deg = Get-NasaValue $parameters.WD10M $date
        precipitation_mm = Get-NasaValue $parameters.PRECTOTCORR $date
        solar_radiation_kwh_m2_day = Get-NasaValue $parameters.ALLSKY_SFC_SW_DWN $date
    })
}
$rows | Export-Csv -LiteralPath $normalizedPath -NoTypeInformation -Encoding utf8

$env:PGPASSWORD = $DbPassword
$psqlArgs = @('-h', $DbHost, '-p', $DbPort, '-U', $DbUser, '-d', $DbName, '-v', 'ON_ERROR_STOP=1')
Write-Host '[3/5] Creating weather tables'
& $psqlCommand.Source @psqlArgs -f (Join-Path $sqlDir '003_weather_schema.sql')
if ($LASTEXITCODE -ne 0) { throw 'Weather schema creation failed.' }

Write-Host '[4/5] Loading normalized CSV into staging'
& $psqlCommand.Source @psqlArgs -c 'TRUNCATE staging.nasa_power_daily;'
if ($LASTEXITCODE -ne 0) { throw 'Weather staging cleanup failed.' }
$localPath = $normalizedPath.Replace('\', '/').Replace("'", "''")
$copySql = "\copy staging.nasa_power_daily (observed_on, longitude, latitude, elevation_m, temperature_c, temperature_max_c, temperature_min_c, relative_humidity_percent, wind_speed_m_s, wind_direction_deg, precipitation_mm, solar_radiation_kwh_m2_day) FROM '$localPath' WITH (FORMAT csv, HEADER true);"
& $psqlCommand.Source @psqlArgs -c $copySql
if ($LASTEXITCODE -ne 0) { throw 'Weather CSV load failed.' }

Write-Host '[5/5] Writing Dixie Fire weather observations and manifest'
& $psqlCommand.Source @psqlArgs -f (Join-Path $sqlDir '004_load_dixie_weather.sql')
if ($LASTEXITCODE -ne 0) { throw 'Dixie Fire weather final load failed.' }

Write-Host "Weather load completed: $($rows.Count) daily observations."
