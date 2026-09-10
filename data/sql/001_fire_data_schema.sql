-- Dixie Fire data layer. Existing application tables are intentionally left unchanged.
CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS firms_hotspot_observations (
    id BIGSERIAL PRIMARY KEY,
    source_record_id VARCHAR(180) NOT NULL UNIQUE,
    event_id VARCHAR(80) NOT NULL REFERENCES fire_events(event_id) ON DELETE CASCADE,
    observed_at TIMESTAMPTZ NOT NULL,
    longitude DOUBLE PRECISION NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    latitude DOUBLE PRECISION NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    location_geom geometry(Point, 4326) NOT NULL,
    satellite VARCHAR(40) NOT NULL,
    instrument VARCHAR(40) NOT NULL,
    confidence_raw VARCHAR(8),
    confidence_score DOUBLE PRECISION,
    brightness_ti4 DOUBLE PRECISION,
    brightness_ti5 DOUBLE PRECISION,
    frp_mw DOUBLE PRECISION,
    scan DOUBLE PRECISION,
    track DOUBLE PRECISION,
    daynight VARCHAR(2),
    hotspot_type INTEGER,
    source_product VARCHAR(80) NOT NULL,
    source_file TEXT NOT NULL,
    in_final_perimeter BOOLEAN NOT NULL DEFAULT FALSE,
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_firms_hotspots_geom
    ON firms_hotspot_observations USING GIST (location_geom);
CREATE INDEX IF NOT EXISTS idx_firms_hotspots_event_time
    ON firms_hotspot_observations (event_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_firms_hotspots_perimeter
    ON firms_hotspot_observations (event_id, in_final_perimeter);

CREATE TABLE IF NOT EXISTS burned_areas (
    id BIGSERIAL PRIMARY KEY,
    event_id VARCHAR(80) NOT NULL REFERENCES fire_events(event_id) ON DELETE CASCADE,
    source_dataset VARCHAR(80) NOT NULL,
    source_event_id VARCHAR(120),
    source_name VARCHAR(200),
    assessment_date DATE,
    area_acres DOUBLE PRECISION,
    area_m2 DOUBLE PRECISION,
    geom geometry(MultiPolygon, 4326) NOT NULL,
    source_crs VARCHAR(80) NOT NULL,
    source_file TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_burned_area_event_source UNIQUE (event_id, source_dataset)
);

CREATE INDEX IF NOT EXISTS idx_burned_areas_geom
    ON burned_areas USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_burned_areas_event
    ON burned_areas (event_id);

CREATE TABLE IF NOT EXISTS fire_hotspots (
    id BIGSERIAL PRIMARY KEY,
    candidate_id VARCHAR(180) NOT NULL UNIQUE,
    event_id VARCHAR(80) NOT NULL REFERENCES fire_events(event_id) ON DELETE CASCADE,
    observed_at TIMESTAMPTZ NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    location_geom geometry(Point, 4326) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'candidate',
    data_owner VARCHAR(120) NOT NULL,
    source_product VARCHAR(80) NOT NULL,
    imagery_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    imagery_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_simulated BOOLEAN NOT NULL DEFAULT FALSE,
    is_replay BOOLEAN NOT NULL DEFAULT TRUE,
    confidence_raw VARCHAR(8),
    confidence_score DOUBLE PRECISION,
    frp_mw DOUBLE PRECISION,
    brightness_ti4 DOUBLE PRECISION,
    brightness_ti5 DOUBLE PRECISION,
    source_file TEXT NOT NULL,
    product_fields JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fire_hotspots_geom
    ON fire_hotspots USING GIST (location_geom);
CREATE INDEX IF NOT EXISTS idx_fire_hotspots_event_time
    ON fire_hotspots (event_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_fire_hotspots_status
    ON fire_hotspots (event_id, status);

CREATE TABLE IF NOT EXISTS fire_hotspot_clusters (
    cluster_id VARCHAR(180) PRIMARY KEY,
    event_id VARCHAR(80) NOT NULL REFERENCES fire_events(event_id) ON DELETE CASCADE,
    observed_at TIMESTAMPTZ NOT NULL,
    grid_x INTEGER NOT NULL,
    grid_y INTEGER NOT NULL,
    center_geom geometry(Point, 4326) NOT NULL,
    point_count INTEGER NOT NULL,
    max_frp_mw DOUBLE PRECISION,
    mean_confidence DOUBLE PRECISION,
    representative_candidate_id VARCHAR(180),
    candidate_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(32) NOT NULL DEFAULT 'candidate',
    imagery_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    is_simulated BOOLEAN NOT NULL DEFAULT FALSE,
    is_replay BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_fire_hotspot_cluster_cell UNIQUE (event_id, observed_at, grid_x, grid_y)
);

CREATE INDEX IF NOT EXISTS idx_fire_hotspot_clusters_geom
    ON fire_hotspot_clusters USING GIST (center_geom);
CREATE INDEX IF NOT EXISTS idx_fire_hotspot_clusters_event_time
    ON fire_hotspot_clusters (event_id, observed_at);

CREATE TABLE IF NOT EXISTS fire_data_manifests (
    dataset_id VARCHAR(160) PRIMARY KEY,
    event_id VARCHAR(80) REFERENCES fire_events(event_id) ON DELETE CASCADE,
    name VARCHAR(240) NOT NULL,
    source_url TEXT NOT NULL,
    license TEXT,
    acquired_at DATE,
    spatial_extent JSONB,
    temporal_extent JSONB,
    source_crs VARCHAR(80),
    target_crs VARCHAR(80),
    processing_steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    sha256 VARCHAR(64),
    local_path TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Staging tables are deliberately recreated by the import script for each run.
CREATE TABLE IF NOT EXISTS staging.firms_raw (
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    bright_ti4 DOUBLE PRECISION,
    scan DOUBLE PRECISION,
    track DOUBLE PRECISION,
    acq_date DATE,
    acq_time INTEGER,
    satellite VARCHAR(40),
    instrument VARCHAR(40),
    confidence VARCHAR(8),
    version VARCHAR(40),
    bright_ti5 DOUBLE PRECISION,
    frp DOUBLE PRECISION,
    daynight VARCHAR(2),
    type INTEGER,
    source_file TEXT
);

CREATE TABLE IF NOT EXISTS staging.mtbs_burn_area (
    ogc_fid BIGSERIAL,
    event_id VARCHAR(254),
    irwinid VARCHAR(254),
    incid_name VARCHAR(254),
    incid_type VARCHAR(254),
    map_id BIGINT,
    map_prog VARCHAR(254),
    asmnt_type VARCHAR(254),
    burnbndac BIGINT,
    burnbndlat VARCHAR(32),
    burnbndlon VARCHAR(32),
    ig_date DATE,
    pre_id VARCHAR(254),
    post_id VARCHAR(254),
    perim_id VARCHAR(254),
    dnbr_offst INTEGER,
    dnbr_stddv INTEGER,
    nodata_t INTEGER,
    incgreen_t INTEGER,
    low_t INTEGER,
    mod_t INTEGER,
    high_t INTEGER,
    comment VARCHAR(254),
    geom geometry(MultiPolygon, 4326)
);
