# Dixie Fire OSM context layers

OSM context layers are currently **deferred**. No processed GeoJSON layer in this
directory should be treated as available yet.

The initial Overpass requests timed out and produced an error response under
`data/raw/osm`. That response is retained for audit purposes, but it is not a
valid OSM dataset and is excluded from the Dixie Fire data manifest.

When a later download succeeds, the expected outputs are:

- `dixie_fire_2021_osm_roads.geojson`: mapped roads and access network.
- `dixie_fire_2021_osm_targets.geojson`: mapped places and selected emergency facilities.
- `dixie_fire_2021_osm_water.geojson`: mapped water bodies and waterways.

The source is OpenStreetMap through the Overpass API. OSM data is volunteer-
mapped and must not be treated as a complete authoritative inventory of roads,
fire stations, hospitals, shelters, or water sources. Reproject the WGS84
GeoJSON layers before metric distance or routing analysis.
