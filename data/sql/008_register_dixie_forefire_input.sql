INSERT INTO fire_data_manifests (
    dataset_id, event_id, name, source_url, license, acquired_at,
    spatial_extent, temporal_extent, source_crs, target_crs,
    processing_steps, local_path
)
VALUES (
    'dixie_fire_2021_forefire_input_manifest',
    'dixie_fire_2021',
    'Dixie Fire ForeFire input preparation manifest',
    'https://github.com/forefireAPI/firefront',
    'Project input manifest; source dataset licenses are recorded per input dataset',
    CURRENT_DATE,
    '{"west": -121.720069, "south": 39.727100, "east": -120.009180, "north": 40.918238, "crs": "EPSG:4326", "buffer_m": 15000}'::jsonb,
    '["2021-07-14T09:11:00Z", "2021-10-25T23:00:00Z"]'::jsonb,
    'EPSG:4326',
    'EPSG:32610',
    '["deterministic ignition candidate selection", "30 m raster input inventory", "NASA POWER hourly weather inventory", "SHA-256 file checksums"]'::jsonb,
    'data/processed/forefire_input/dixie_fire_2021_forefire_input_manifest.json'
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
