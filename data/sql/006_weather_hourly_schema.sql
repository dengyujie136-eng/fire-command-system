CREATE TABLE IF NOT EXISTS weather_hourly_observations (
    id BIGSERIAL PRIMARY KEY,
    event_id VARCHAR(80) NOT NULL REFERENCES fire_events(event_id) ON DELETE CASCADE,
    observed_at TIMESTAMPTZ NOT NULL,
    observed_on DATE NOT NULL,
    longitude DOUBLE PRECISION NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    latitude DOUBLE PRECISION NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    elevation_m DOUBLE PRECISION,
    location_geom geometry(Point, 4326) NOT NULL,
    temperature_c DOUBLE PRECISION,
    relative_humidity_percent DOUBLE PRECISION,
    wind_speed_m_s DOUBLE PRECISION,
    wind_direction_deg DOUBLE PRECISION,
    wind_u_m_s DOUBLE PRECISION,
    wind_v_m_s DOUBLE PRECISION,
    precipitation_mm DOUBLE PRECISION,
    solar_radiation_mj_m2_h DOUBLE PRECISION,
    is_interpolated BOOLEAN NOT NULL DEFAULT FALSE,
    source_dataset VARCHAR(80) NOT NULL,
    source_file TEXT NOT NULL,
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_weather_hourly_event_source_time UNIQUE (event_id, source_dataset, observed_at)
);

CREATE INDEX IF NOT EXISTS idx_weather_hourly_event_time
    ON weather_hourly_observations (event_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_weather_hourly_geom
    ON weather_hourly_observations USING GIST (location_geom);

CREATE TABLE IF NOT EXISTS staging.nasa_power_hourly (
    timestamp_utc TIMESTAMPTZ,
    observed_on DATE,
    longitude DOUBLE PRECISION,
    latitude DOUBLE PRECISION,
    elevation_m DOUBLE PRECISION,
    temperature_c DOUBLE PRECISION,
    relative_humidity_percent DOUBLE PRECISION,
    wind_speed_m_s DOUBLE PRECISION,
    wind_direction_deg DOUBLE PRECISION,
    wind_u_m_s DOUBLE PRECISION,
    wind_v_m_s DOUBLE PRECISION,
    precipitation_mm DOUBLE PRECISION,
    solar_radiation_mj_m2_h DOUBLE PRECISION,
    is_interpolated BOOLEAN,
    source_dataset VARCHAR(80)
);
