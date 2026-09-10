INSERT INTO fire_data_manifests (
    dataset_id, event_id, name, source_url, license, acquired_at,
    spatial_extent, temporal_extent, source_crs, target_crs,
    processing_steps, local_path
)
VALUES
(
    'dixie_fire_2021_copernicus_dem_glo30',
    'dixie_fire_2021',
    'Dixie Fire Copernicus DEM GLO-30 AOI product',
    'https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-digital-elevation-model',
    'Copernicus DEM license',
    CURRENT_DATE,
    '{"west": -121.720069, "south": 39.727100, "east": -120.009180, "north": 40.918238, "crs": "EPSG:4326", "buffer_m": 15000}'::jsonb,
    '["2021-07-13", "2021-10-25"]'::jsonb,
    'EPSG:4326',
    'EPSG:32610',
    '["MTBS perimeter plus 15 km buffer", "four COG tiles mosaicked", "reprojected to UTM zone 10N", "resampled to 30 m", "GeoTIFF output"]'::jsonb,
    'data/processed/dem/dixie_fire_2021_copernicus_dem_30m_utm10.tif'
),
(
    'dixie_fire_2021_esa_worldcover_2021',
    'dixie_fire_2021',
    'Dixie Fire ESA WorldCover 2021 AOI product',
    'https://esa-worldcover.org/en/data-access',
    'ESA WorldCover license',
    CURRENT_DATE,
    '{"west": -121.720069, "south": 39.727100, "east": -120.009180, "north": 40.918238, "crs": "EPSG:4326", "buffer_m": 15000}'::jsonb,
    '["2021-01-01", "2021-12-31"]'::jsonb,
    'EPSG:4326',
    'EPSG:32610',
    '["MTBS perimeter plus 15 km buffer", "10 m COG source", "reprojected to UTM zone 10N", "nearest-neighbour resampled to 30 m", "mapped to simplified fuel classes", "GeoTIFF output"]'::jsonb,
    'data/processed/fuel/dixie_fire_2021_worldcover_30m_utm10.tif'
)
ON CONFLICT (dataset_id) DO UPDATE SET
    name = EXCLUDED.name,
    source_url = EXCLUDED.source_url,
    license = EXCLUDED.license,
    acquired_at = EXCLUDED.acquired_at,
    spatial_extent = EXCLUDED.spatial_extent,
    temporal_extent = EXCLUDED.temporal_extent,
    source_crs = EXCLUDED.source_crs,
    target_crs = EXCLUDED.target_crs,
    processing_steps = EXCLUDED.processing_steps,
    local_path = EXCLUDED.local_path;
