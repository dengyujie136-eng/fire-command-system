BEGIN;

DELETE FROM weather_observations WHERE event_id = 'dixie_fire_2021';

INSERT INTO weather_observations (
    event_id, observed_on, longitude, latitude, elevation_m, location_geom,
    temperature_c, temperature_max_c, temperature_min_c,
    relative_humidity_percent, wind_speed_m_s, wind_direction_deg,
    precipitation_mm, solar_radiation_kwh_m2_day,
    source_dataset, source_file, attributes
)
SELECT
    'dixie_fire_2021', observed_on, longitude, latitude, elevation_m,
    ST_SetSRID(ST_MakePoint(longitude, latitude), 4326),
    temperature_c, temperature_max_c, temperature_min_c,
    relative_humidity_percent, wind_speed_m_s, wind_direction_deg,
    precipitation_mm, solar_radiation_kwh_m2_day,
    'NASA_POWER_DAILY',
    'data/raw/weather/dixie_fire_2021_nasa_power_daily.json',
    jsonb_build_object(
        'community', 'AG',
        'time_standard', 'UTC',
        'point_role', 'Dixie Fire ignition-area representative point'
    )
FROM staging.nasa_power_daily;

INSERT INTO fire_data_manifests (
    dataset_id, event_id, name, source_url, license, acquired_at,
    spatial_extent, temporal_extent, source_crs, target_crs,
    processing_steps, local_path
)
VALUES (
    'dixie_fire_2021_nasa_power_daily',
    'dixie_fire_2021',
    'Dixie Fire NASA POWER daily meteorological baseline',
    'https://power.larc.nasa.gov/',
    'NASA POWER data access terms',
    CURRENT_DATE,
    '{"longitude": -121.38241, "latitude": 39.87194, "crs": "EPSG:4326"}'::jsonb,
    '["2021-07-13", "2021-10-25"]'::jsonb,
    'EPSG:4326',
    'EPSG:4326',
    '["NASA POWER daily point query", "UTC time standard", "JSON to normalized CSV", "point geometry creation"]'::jsonb,
    'data/raw/weather/dixie_fire_2021_nasa_power_daily.json'
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

COMMIT;
