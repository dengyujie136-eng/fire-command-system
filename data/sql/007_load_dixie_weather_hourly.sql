BEGIN;

DELETE FROM weather_hourly_observations WHERE event_id = 'dixie_fire_2021';

INSERT INTO weather_hourly_observations (
    event_id, observed_at, observed_on, longitude, latitude, elevation_m, location_geom,
    temperature_c, relative_humidity_percent, wind_speed_m_s, wind_direction_deg,
    wind_u_m_s, wind_v_m_s, precipitation_mm, solar_radiation_mj_m2_h,
    is_interpolated, source_dataset, source_file, attributes
)
SELECT
    'dixie_fire_2021', timestamp_utc, observed_on, longitude, latitude, elevation_m,
    ST_SetSRID(ST_MakePoint(longitude, latitude), 4326),
    temperature_c, relative_humidity_percent, wind_speed_m_s, wind_direction_deg,
    wind_u_m_s, wind_v_m_s, precipitation_mm, solar_radiation_mj_m2_h,
    COALESCE(is_interpolated, FALSE),
    'NASA_POWER_HOURLY',
    'data/raw/weather/dixie_fire_2021_nasa_power_hourly.json',
    jsonb_build_object(
        'normalized_file', 'data/processed/weather/dixie_fire_2021_nasa_power_hourly.csv',
        'community', 'AG',
        'time_standard', 'UTC',
        'interval_minutes', 60,
        'point_role', 'Dixie Fire ignition-area representative point',
        'precipitation_status', 'missing_in_source'
    )
FROM staging.nasa_power_hourly;

INSERT INTO fire_data_manifests (
    dataset_id, event_id, name, source_url, license, acquired_at,
    spatial_extent, temporal_extent, source_crs, target_crs,
    processing_steps, local_path
)
VALUES (
    'dixie_fire_2021_nasa_power_hourly',
    'dixie_fire_2021',
    'Dixie Fire NASA POWER hourly meteorological input',
    'https://power.larc.nasa.gov/',
    'NASA POWER data access terms',
    CURRENT_DATE,
    '{"longitude": -121.38241, "latitude": 39.87194, "crs": "EPSG:4326"}'::jsonb,
    '["2021-07-13T00:00:00Z", "2021-10-25T23:00:00Z"]'::jsonb,
    'EPSG:4326',
    'EPSG:4326',
    '["NASA POWER hourly point query", "UTC time standard", "JSON to normalized CSV", "wind component derivation", "no interpolation"]'::jsonb,
    'data/processed/weather/dixie_fire_2021_nasa_power_hourly.csv'
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
