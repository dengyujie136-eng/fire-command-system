param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$OverpassUrl = 'https://overpass.kumi.systems/api/interpreter'
)

$ErrorActionPreference = 'Stop'
$rawDir = Join-Path $RepoRoot 'data\raw\osm'
$processedDir = Join-Path $RepoRoot 'data\processed\osm'
$rawPath = Join-Path $rawDir 'dixie_fire_2021_osm_overpass.json'
$rawRoadsPath = Join-Path $rawDir 'dixie_fire_2021_osm_roads_overpass.json'
$rawTargetsPath = Join-Path $rawDir 'dixie_fire_2021_osm_targets_overpass.json'
$rawWaterPath = Join-Path $rawDir 'dixie_fire_2021_osm_water_overpass.json'
$roadsPath = Join-Path $processedDir 'dixie_fire_2021_osm_roads.geojson'
$targetsPath = Join-Path $processedDir 'dixie_fire_2021_osm_targets.geojson'
$waterPath = Join-Path $processedDir 'dixie_fire_2021_osm_water.geojson'
$metadataPath = Join-Path $processedDir 'dixie_fire_2021_osm_metadata.json'

$west = -121.720069
$south = 39.727100
$east = -120.009180
$north = 40.918238
$bbox = "$south,$west,$north,$east"
$midLongitude = ($west + $east) / 2
$midLatitude = ($south + $north) / 2

New-Item -ItemType Directory -Force -Path $rawDir, $processedDir | Out-Null

Write-Host '[1/3] Downloading OSM context data from Overpass in three layers'
$curl = Get-Command curl.exe -ErrorAction SilentlyContinue
if (-not $curl) { throw 'curl.exe is required for the Overpass download.' }

function Invoke-OverpassLayer([string]$Query, [string]$Path) {
    & $curl.Source -L --fail-with-body --max-time 300 -A 'fire-command-system/0.1' --get --data-urlencode "data=$Query" $OverpassUrl -o $Path
    if ($LASTEXITCODE -ne 0) { throw "Overpass request failed for $Path with exit code $LASTEXITCODE" }
    return (Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json)
}

$tiles = @(
    @{ name = 'sw'; south = $south; west = $west; north = $midLatitude; east = $midLongitude },
    @{ name = 'se'; south = $south; west = $midLongitude; north = $midLatitude; east = $east },
    @{ name = 'nw'; south = $midLatitude; west = $west; north = $north; east = $midLongitude },
    @{ name = 'ne'; south = $midLatitude; west = $midLongitude; north = $north; east = $east }
)
$roadElements = New-Object System.Collections.Generic.List[object]
$targetElements = New-Object System.Collections.Generic.List[object]
$waterElements = New-Object System.Collections.Generic.List[object]

foreach ($tile in $tiles) {
    $tileBbox = "$($tile.south),$($tile.west),$($tile.north),$($tile.east)"
    $roadsQuery = @"
[out:json][timeout:180];
(
  way["highway"="primary"]($tileBbox);
  way["highway"="secondary"]($tileBbox);
  way["highway"="tertiary"]($tileBbox);
  way["highway"="unclassified"]($tileBbox);
  way["highway"="residential"]($tileBbox);
  way["highway"="service"]($tileBbox);
  way["highway"="track"]($tileBbox);
);
out body geom;
"@
    $targetsQuery = @"
[out:json][timeout:180];
(
  node["place"]($tileBbox);
  way["place"]($tileBbox);
  node["amenity"="fire_station"]($tileBbox);
  node["amenity"="hospital"]($tileBbox);
  node["amenity"="shelter"]($tileBbox);
  way["amenity"="fire_station"]($tileBbox);
  way["amenity"="hospital"]($tileBbox);
  way["amenity"="shelter"]($tileBbox);
);
out body geom;
"@
    $waterQuery = @"
[out:json][timeout:180];
(
  node["natural"="water"]($tileBbox);
  way["natural"="water"]($tileBbox);
  way["waterway"]($tileBbox);
);
out body geom;
"@
    $roadsTilePath = Join-Path $env:TEMP "dixie_osm_roads_$($tile.name).json"
    $targetsTilePath = Join-Path $env:TEMP "dixie_osm_targets_$($tile.name).json"
    $waterTilePath = Join-Path $env:TEMP "dixie_osm_water_$($tile.name).json"
    Write-Host "  tile $($tile.name): roads"
    $roadsOsm = Invoke-OverpassLayer $roadsQuery $roadsTilePath
    Write-Host "  tile $($tile.name): targets"
    $targetsOsm = Invoke-OverpassLayer $targetsQuery $targetsTilePath
    Write-Host "  tile $($tile.name): water"
    $waterOsm = Invoke-OverpassLayer $waterQuery $waterTilePath
    foreach ($element in @($roadsOsm.elements)) { $roadElements.Add($element) }
    foreach ($element in @($targetsOsm.elements)) { $targetElements.Add($element) }
    foreach ($element in @($waterOsm.elements)) { $waterElements.Add($element) }
}

function Remove-DuplicateElements([object[]]$Elements) {
    $seen = @{}
    $unique = New-Object System.Collections.Generic.List[object]
    foreach ($element in $Elements) {
        $key = "$($element.type):$($element.id)"
        if (-not $seen.ContainsKey($key)) {
            $seen[$key] = $true
            $unique.Add($element)
        }
    }
    return @($unique)
}

$roadsElements = Remove-DuplicateElements @($roadElements)
$targetElements = Remove-DuplicateElements @($targetElements)
$waterElements = Remove-DuplicateElements @($waterElements)
$roadsLayer = [ordered]@{ version = 0.6; generator = 'fire-command-system'; elements = $roadsElements }
$targetsLayer = [ordered]@{ version = 0.6; generator = 'fire-command-system'; elements = $targetElements }
$waterLayer = [ordered]@{ version = 0.6; generator = 'fire-command-system'; elements = $waterElements }
[IO.File]::WriteAllText($rawRoadsPath, ($roadsLayer | ConvertTo-Json -Depth 20), (New-Object System.Text.UTF8Encoding($false)))
[IO.File]::WriteAllText($rawTargetsPath, ($targetsLayer | ConvertTo-Json -Depth 20), (New-Object System.Text.UTF8Encoding($false)))
[IO.File]::WriteAllText($rawWaterPath, ($waterLayer | ConvertTo-Json -Depth 20), (New-Object System.Text.UTF8Encoding($false)))
$allElements = @($roadsElements) + @($targetElements) + @($waterElements)
$combined = [ordered]@{ version = 0.6; generator = 'fire-command-system'; elements = $allElements }
[IO.File]::WriteAllText($rawPath, ($combined | ConvertTo-Json -Depth 20), (New-Object System.Text.UTF8Encoding($false)))
$osm = $combined

function Get-Tag([object]$Tags, [string]$Name) {
    if ($null -eq $Tags) { return $null }
    $property = $Tags.PSObject.Properties[$Name]
    if ($property) { return [string]$property.Value }
    return $null
}

function Get-Point([object]$Element) {
    if ($null -ne $Element.lat -and $null -ne $Element.lon) {
        return @([double]$Element.lon, [double]$Element.lat)
    }
    $geometry = @($Element.geometry)
    if ($geometry.Count -eq 0) { return $null }
    $longitude = ($geometry | Measure-Object lon -Average).Average
    $latitude = ($geometry | Measure-Object lat -Average).Average
    return @([double]$longitude, [double]$latitude)
}

function New-PointFeature([object]$Element, [string]$Category) {
    $point = Get-Point $Element
    if ($null -eq $point) { return $null }
    $properties = [ordered]@{ osm_id = $Element.id; category = $Category }
    foreach ($tag in @('name', 'place', 'amenity', 'emergency', 'population', 'operator', 'water')) {
        $value = Get-Tag $Element.tags $tag
        if ($null -ne $value) { $properties[$tag] = $value }
    }
    return [ordered]@{
        type = 'Feature'
        properties = $properties
        geometry = [ordered]@{ type = 'Point'; coordinates = $point }
    }
}

function New-WayFeature([object]$Element, [string]$Category) {
    $geometry = @($Element.geometry)
    if ($geometry.Count -lt 2) { return $null }
    $coordinates = @($geometry | ForEach-Object { @([double]$_.lon, [double]$_.lat) })
    $properties = [ordered]@{ osm_id = $Element.id; category = $Category }
    foreach ($tag in @('name', 'highway', 'surface', 'ref', 'place', 'amenity', 'natural', 'waterway', 'water', 'access')) {
        $value = Get-Tag $Element.tags $tag
        if ($null -ne $value) { $properties[$tag] = $value }
    }
    $isClosed = ($coordinates.Count -ge 4 -and ($coordinates[0][0] -eq $coordinates[-1][0]) -and ($coordinates[0][1] -eq $coordinates[-1][1]))
    $geometryType = if ($Category -eq 'water' -and $isClosed) { 'Polygon' } else { 'LineString' }
    $geometryCoordinates = if ($geometryType -eq 'Polygon') { ,$coordinates } else { $coordinates }
    return [ordered]@{
        type = 'Feature'
        properties = $properties
        geometry = [ordered]@{ type = $geometryType; coordinates = $geometryCoordinates }
    }
}

$roads = New-Object System.Collections.Generic.List[object]
$targets = New-Object System.Collections.Generic.List[object]
$water = New-Object System.Collections.Generic.List[object]
foreach ($element in @($osm.elements)) {
    $highway = Get-Tag $element.tags 'highway'
    $place = Get-Tag $element.tags 'place'
    $amenity = Get-Tag $element.tags 'amenity'
    $natural = Get-Tag $element.tags 'natural'
    $waterway = Get-Tag $element.tags 'waterway'

    if ($null -ne $highway) {
        $feature = New-WayFeature $element 'road'
        if ($null -ne $feature) { $roads.Add($feature) }
    }
    if ($null -ne $place -or $null -ne $amenity) {
        $category = if ($null -ne $amenity) { "amenity:$amenity" } else { "place:$place" }
        $feature = if ($null -ne $element.lat) { New-PointFeature $element $category } else { New-WayFeature $element $category }
        if ($null -ne $feature) { $targets.Add($feature) }
    }
    if ($natural -eq 'water' -or $null -ne $waterway) {
        $category = if ($natural -eq 'water') { 'water' } else { 'waterway' }
        $feature = if ($null -ne $element.lat) { New-PointFeature $element $category } else { New-WayFeature $element $category }
        if ($null -ne $feature) { $water.Add($feature) }
    }
}

function Write-FeatureCollection([string]$Path, [object[]]$Features) {
    $collection = [ordered]@{
        type = 'FeatureCollection'
        features = @($Features)
    }
    [IO.File]::WriteAllText($Path, ($collection | ConvertTo-Json -Depth 20), (New-Object System.Text.UTF8Encoding($false)))
}

Write-Host '[2/3] Writing processed GeoJSON layers'
Write-FeatureCollection $roadsPath @($roads)
Write-FeatureCollection $targetsPath @($targets)
Write-FeatureCollection $waterPath @($water)

$metadata = [ordered]@{
    schema_version = 'fire.osm.context.v0.1'
    event_id = 'dixie_fire_2021'
    source = 'OpenStreetMap via Overpass API'
    source_url = $OverpassUrl
    license = 'OpenStreetMap ODbL; attribution required'
    query_bbox = [ordered]@{ west = $west; south = $south; east = $east; north = $north; crs = 'EPSG:4326' }
    query = [ordered]@{
        mode = 'four spatial tiles per layer'
        layers = @('roads: highway primary, secondary, tertiary, unclassified, residential, service, track', 'targets: place plus fire_station, hospital, shelter amenities', 'water: natural=water and waterway')
    }
    raw_path = 'data/raw/osm/dixie_fire_2021_osm_overpass.json'
    raw_layer_paths = @(
        'data/raw/osm/dixie_fire_2021_osm_roads_overpass.json'
        'data/raw/osm/dixie_fire_2021_osm_targets_overpass.json'
        'data/raw/osm/dixie_fire_2021_osm_water_overpass.json'
    )
    outputs = @(
        [ordered]@{ path = 'data/processed/osm/dixie_fire_2021_osm_roads.geojson'; role = 'roads and access network'; feature_count = $roads.Count }
        [ordered]@{ path = 'data/processed/osm/dixie_fire_2021_osm_targets.geojson'; role = 'places and emergency facilities'; feature_count = $targets.Count }
        [ordered]@{ path = 'data/processed/osm/dixie_fire_2021_osm_water.geojson'; role = 'water bodies and waterways'; feature_count = $water.Count }
    )
    notes = @(
        'OSM coverage is volunteer-mapped and may be incomplete in remote forest areas.'
        'These layers are contextual decision-support data, not authoritative emergency resource inventories.'
        'Geometry is kept in WGS84 GeoJSON for exchange; reproject before metric distance or routing analysis.'
    )
}
[IO.File]::WriteAllText($metadataPath, ($metadata | ConvertTo-Json -Depth 20), (New-Object System.Text.UTF8Encoding($false)))

Write-Host '[3/3] OSM context download completed'
Write-Host "Roads: $($roads.Count)"
Write-Host "Targets: $($targets.Count)"
Write-Host "Water: $($water.Count)"
