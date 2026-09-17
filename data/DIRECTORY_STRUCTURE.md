# Dixie Fire data directory

This directory stores metadata, source data references, and local processing outputs for the Dixie Fire event.

```text
data/
├── raw/
│   ├── firms/          NASA FIRMS hotspot products
│   ├── burned_area/    Existing burned-area or official perimeter products
│   ├── sentinel2/      Sentinel-2 source imagery
│   ├── weather/        ERA5, NASA POWER, or other weather data
│   ├── dem/            SRTM or Copernicus DEM source data
│   ├── fuel/           ESA WorldCover or other fuel/land-cover data
│   ├── osm/            OpenStreetMap roads, buildings, and facilities
│   └── himawari/       Himawari historical frames for replay
├── interim/
│   ├── clipped/        Data clipped to the Dixie Fire study area
│   ├── reprojected/    Data converted to the required CRS
│   └── normalized/     Cleaned and schema-normalized data
├── processed/
│   ├── hotspots/       Database-ready hotspot products
│   ├── burned_area/    Database-ready burned-area products
│   ├── forefire_input/ ForeFire-ready DEM, fuel, and weather inputs
│   └── realtime_products/ 10-minute historical replay products
├── samples/            Small files suitable for Git or demonstrations
└── manifests/          Dataset metadata, licenses, sources, and checksums
```

Large rasters, videos, and downloaded archives must not be committed to Git. Keep their source URL, local path, acquisition time, CRS, spatial and temporal extent, processing steps, license, and SHA-256 checksum in a manifest under `data/manifests/`.

The first complete event uses the stable identifier:

```text
event_id: dixie_fire_2021
event_name: Dixie Fire
```
