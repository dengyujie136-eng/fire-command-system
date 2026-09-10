CREATE TABLE IF NOT EXISTS weather_observations (
    id BIGSERIAL PRIMARY KEY,
    event_id VARCHAR(80) NOT NULL REFERENCES fire_events(event_id) ON DELETE CASCADE,
    observed_on DATE NOT NULL,
    longitude DOUBLE PRECISION NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    latitude DOUBLE PRECISION NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    elevation_m DOUBLE PRECISION,
    location_geom geometry(Point, 4326) NOT NULL,
    temperature_c DOUBLE PRECISION,
    temperature_max_c DOUBLE PRECISION,
    temperature_min_c DOUBLE PRECISION,
    relative_humidity_percent DOUBLE PRECISION,
    wind_speed_m_s DOUBLE PRECISION,
    wind_direction_deg DOUBLE PRECISION,
    precipitation_mm DOUBLE PRECISION,
    solar_radiation_kwh_m2_day DOUBLE PRECISION,
    source_dataset VARCHAR(80) NOT NULL,
    source_file TEXT NOT NULL,
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_weather_event_source_day UNIQUE (event_id, source_dataset, observed_on)
);

CREATE INDEX IF NOT EXISTS idx_weather_event_day
    ON weather_observations (event_id, observed_on);
CREATE INDEX IF NOT EXISTS idx_weather_geom
    ON weather_observations USING GIST (location_geom);

CREATE TABLE IF NOT EXISTS staging.nasa_power_daily (
    observed_on DATE,
    longitude DOUBLE PRECISION,
    latitude DOUBLE PRECISION,
    elevation_m DOUBLE PRECISION,
    temperature_c DOUBLE PRECISION,
    temperature_max_c DOUBLE PRECISION,
    temperature_min_c DOUBLE PRECISION,
    relative_humidity_percent DOUBLE PRECISION,
    wind_speed_m_s DOUBLE PRECISION,
    wind_direction_deg DOUBLE PRECISION,
    precipitation_mm DOUBLE PRECISION,
    solar_radiation_kwh_m2_day DOUBLE PRECISION
);
