param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
)

$ErrorActionPreference = 'Stop'
$rawPath = Join-Path $RepoRoot 'data\raw\weather\dixie_fire_2021_nasa_power_hourly.json'
$processedDir = Join-Path $RepoRoot 'data\processed\weather'
$csvPath = Join-Path $processedDir 'dixie_fire_2021_nasa_power_hourly.csv'
$metadataPath = Join-Path $processedDir 'dixie_fire_2021_nasa_power_hourly_metadata.json'

if (-not (Test-Path -LiteralPath $rawPath)) {
    throw "NASA POWER hourly JSON not found: $rawPath"
}

New-Item -ItemType Directory -Force -Path $processedDir | Out-Null
$json = Get-Content -LiteralPath $rawPath -Raw | ConvertFrom-Json
$parameter = $json.properties.parameter
$timestamps = @($parameter.T2M.PSObject.Properties.Name | Sort-Object)

function Get-Value([object]$series, [string]$timestamp) {
    $property = $series.PSObject.Properties[$timestamp]
    if (-not $property) { return $null }
    $value = [double]$property.Value
    if ($value -le -900) { return $null }
    return $value
}

function Get-NumberOrNull([object]$value) {
    if ($null -eq $value) { return $null }
    return [double]$value
}

$rows = New-Object System.Collections.Generic.List[object]
$missingCounts = [ordered]@{}
$fields = @('T2M', 'RH2M', 'WS10M', 'WD10M', 'PRECTOTCORR', 'ALLSKY_SFC_SW_DWN')
foreach ($field in $fields) { $missingCounts[$field] = 0 }

foreach ($timestamp in $timestamps) {
    $year = [int]$timestamp.Substring(0, 4)
    $month = [int]$timestamp.Substring(4, 2)
    $day = [int]$timestamp.Substring(6, 2)
    $hour = [int]$timestamp.Substring(8, 2)
    $dateTime = [datetime]::new($year, $month, $day, $hour, 0, 0, [DateTimeKind]::Utc)

    $values = [ordered]@{}
    foreach ($field in $fields) {
        $value = Get-Value $parameter.$field $timestamp
        if ($null -eq $value) { $missingCounts[$field]++ }
        $values[$field] = $value
    }

    $speed = Get-NumberOrNull $values['WS10M']
    $direction = Get-NumberOrNull $values['WD10M']
    $windU = $null
    $windV = $null
    if ($null -ne $speed -and $null -ne $direction) {
        $radians = $direction * [Math]::PI / 180.0
        $windU = [Math]::Round($speed * [Math]::Sin($radians), 6)
        $windV = [Math]::Round($speed * [Math]::Cos($radians), 6)
    }

    $rows.Add([PSCustomObject][ordered]@{
        timestamp_utc = $dateTime.ToString('yyyy-MM-ddTHH:mm:ssZ')
        observed_on = $dateTime.ToString('yyyy-MM-dd')
        longitude = [double]$json.geometry.coordinates[0]
        latitude = [double]$json.geometry.coordinates[1]
        elevation_m = [double]$json.geometry.coordinates[2]
        temperature_c = $values['T2M']
        relative_humidity_percent = $values['RH2M']
        wind_speed_m_s = $values['WS10M']
        wind_direction_deg = $values['WD10M']
        wind_u_m_s = $windU
        wind_v_m_s = $windV
        precipitation_mm = $values['PRECTOTCORR']
        solar_radiation_mj_m2_h = $values['ALLSKY_SFC_SW_DWN']
        is_interpolated = $false
        source_dataset = 'NASA_POWER_hourly'
    })
}

$rows | Export-Csv -LiteralPath $csvPath -NoTypeInformation -Encoding utf8
$sourceUrl = 'https://power.larc.nasa.gov/api/temporal/hourly/point?parameters=T2M,RH2M,WS10M,WD10M,PRECTOTCORR,ALLSKY_SFC_SW_DWN&community=AG&longitude=-121.38241&latitude=39.87194&start=20210713&end=20211025&format=JSON&time-standard=UTC'
$metadata = [ordered]@{
    schema_version = 'fire.weather.hourly.metadata.v0.1'
    event_id = 'dixie_fire_2021'
    source_dataset = 'NASA_POWER_hourly'
    source_url = $sourceUrl
    time_standard = 'UTC'
    interval_minutes = 60
    is_interpolated = $false
    row_count = $rows.Count
    start_at = $rows[0].timestamp_utc
    end_at = $rows[$rows.Count - 1].timestamp_utc
    point = [ordered]@{
        longitude = [double]$json.geometry.coordinates[0]
        latitude = [double]$json.geometry.coordinates[1]
        elevation_m = [double]$json.geometry.coordinates[2]
        crs = 'EPSG:4326'
    }
    missing_value_counts = $missingCounts
    notes = @(
        'This file is normalized from the raw NASA POWER hourly response and does not replace the daily dataset.'
        'Values at or below -900 in the NASA POWER response are represented as empty CSV values.'
        'Wind components use the same trigonometric convention as the current ForeFire adapter.'
        'No temporal interpolation has been applied.'
    )
}
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($metadataPath, ($metadata | ConvertTo-Json -Depth 10), $utf8NoBom)

Write-Host "Hourly weather CSV: $csvPath"
Write-Host "Hourly weather metadata: $metadataPath"
Write-Host "Rows: $($rows.Count)"
