BEGIN;

-- Rebuild only the Dixie Fire data-layer records. Existing application data is untouched.
DELETE FROM fire_hotspots WHERE event_id = 'dixie_fire_2021';
DELETE FROM fire_hotspot_clusters WHERE event_id = 'dixie_fire_2021';
DELETE FROM firms_hotspot_observations WHERE event_id = 'dixie_fire_2021';
DELETE FROM burned_areas WHERE event_id = 'dixie_fire_2021';

WITH perimeter AS (
    SELECT *
    FROM staging.mtbs_burn_area
    WHERE UPPER(COALESCE(incid_name, '')) = 'DIXIE'
    ORDER BY ogc_fid
    LIMIT 1
), first_point AS (
    SELECT f.*
    FROM staging.firms_raw f
    CROSS JOIN perimeter p
    WHERE ST_Covers(p.geom, ST_SetSRID(ST_MakePoint(f.longitude, f.latitude), 4326))
    ORDER BY f.acq_date, f.acq_time, f.latitude, f.longitude
    LIMIT 1
), fallback_point AS (
    SELECT
        COALESCE((SELECT longitude FROM first_point), ST_X(ST_PointOnSurface(p.geom))) AS longitude,
        COALESCE((SELECT latitude FROM first_point), ST_Y(ST_PointOnSurface(p.geom))) AS latitude,
        COALESCE(
            to_timestamp((SELECT acq_date::text || lpad(acq_time::text, 4, '0') FROM first_point), 'YYYY-MM-DDHH24MI') AT TIME ZONE 'UTC',
            TIMESTAMPTZ '2021-07-13 00:00:00+00'
        ) AS started_at
    FROM perimeter p
)
INSERT INTO fire_events (
    event_id, name, status, scenario_id, source_mode,
    ignition_longitude, ignition_latitude, ignition_confidence,
    started_at, closed_at, metadata_json
)
SELECT
    'dixie_fire_2021',
    'Dixie Fire',
    'archived',
    'dixie_fire_2021',
    'historical',
    longitude,
    latitude,
    0.0,
    started_at,
    TIMESTAMPTZ '2021-10-25 23:59:59+00',
    json_build_object(
        'event_name', 'Dixie Fire',
        'country', 'United States',
        'region', 'California',
        'is_simulated', false,
        'data_source_mode', 'historical',
        'firms_product', 'VIIRS_SNPP_SP',
        'mtbs_product', 'burn_area',
        'study_event_period', json_build_array('2021-07-13', '2021-10-25')
    )
FROM fallback_point
ON CONFLICT (event_id) DO UPDATE SET
    name = EXCLUDED.name,
    status = EXCLUDED.status,
    scenario_id = EXCLUDED.scenario_id,
    source_mode = EXCLUDED.source_mode,
    ignition_longitude = EXCLUDED.ignition_longitude,
    ignition_latitude = EXCLUDED.ignition_latitude,
    started_at = EXCLUDED.started_at,
    closed_at = EXCLUDED.closed_at,
    metadata_json = EXCLUDED.metadata_json,
    updated_at = now();

INSERT INTO burned_areas (
    event_id, source_dataset, source_event_id, source_name,
    assessment_date, area_acres, area_m2, geom, source_crs,
    source_file, metadata
)
SELECT
    'dixie_fire_2021',
    'MTBS',
    p.event_id,
    p.incid_name,
    p.ig_date,
    p.burnbndac,
    ST_Area(ST_Transform(ST_Multi(ST_CollectionExtract(ST_MakeValid(p.geom), 3)), 5070)),
    ST_Multi(ST_CollectionExtract(ST_MakeValid(p.geom), 3)),
    'EPSG:5070',
    'data/raw/burned_area/dixie_fire_2021_mtbs_burn_area/',
    json_build_object(
        'map_id', p.map_id,
        'irwinid', p.irwinid,
        'perim_id', p.perim_id,
        'assessment_type', p.asmnt_type,
        'pre_id', p.pre_id,
        'post_id', p.post_id
    )
FROM staging.mtbs_burn_area p
WHERE UPPER(COALESCE(p.incid_name, '')) = 'DIXIE';

INSERT INTO firms_hotspot_observations (
    source_record_id, event_id, observed_at, longitude, latitude,
    location_geom, satellite, instrument, confidence_raw, confidence_score,
    brightness_ti4, brightness_ti5, frp_mw, scan, track, daynight,
    hotspot_type, source_product, source_file, in_final_perimeter, attributes
)
SELECT
    'dixie_fire_2021-firms-viirs_snpp-' ||
    to_char(to_timestamp(f.acq_date::text || lpad(f.acq_time::text, 4, '0'), 'YYYY-MM-DDHH24MI') AT TIME ZONE 'UTC', 'YYYYMMDD"T"HH24MISS"Z"') || '-' ||
    to_char(round(f.latitude::numeric, 6), 'FM9990.000000') || '-' ||
    to_char(round(f.longitude::numeric, 6), 'FM990.000000'),
    'dixie_fire_2021',
    to_timestamp(f.acq_date::text || lpad(f.acq_time::text, 4, '0'), 'YYYY-MM-DDHH24MI') AT TIME ZONE 'UTC',
    f.longitude,
    f.latitude,
    ST_SetSRID(ST_MakePoint(f.longitude, f.latitude), 4326),
    f.satellite,
    f.instrument,
    f.confidence,
    CASE lower(f.confidence) WHEN 'h' THEN 0.90 WHEN 'n' THEN 0.50 WHEN 'l' THEN 0.30 ELSE NULL END,
    f.bright_ti4,
    f.bright_ti5,
    f.frp,
    f.scan,
    f.track,
    f.daynight,
    f.type,
    'VIIRS_SNPP_SP',
    f.source_file,
    EXISTS (
        SELECT 1 FROM burned_areas b
        WHERE b.event_id = 'dixie_fire_2021'
          AND ST_Covers(b.geom, ST_SetSRID(ST_MakePoint(f.longitude, f.latitude), 4326))
    ),
    json_build_object(
        'version', f.version,
        'source_confidence', f.confidence,
        'acq_time_utc', lpad(f.acq_time::text, 4, '0')
    )
FROM staging.firms_raw f;

INSERT INTO fire_hotspots (
    candidate_id, event_id, observed_at, longitude, latitude,
    location_geom, status, data_owner, source_product,
    imagery_status, imagery_refs, is_simulated, is_replay,
    confidence_raw, confidence_score, frp_mw, brightness_ti4,
    brightness_ti5, source_file, product_fields
)
SELECT
    o.source_record_id,
    o.event_id,
    o.observed_at,
    o.longitude,
    o.latitude,
    o.location_geom,
    'candidate',
    'NASA FIRMS',
    o.source_product,
    'pending',
    '[]'::jsonb,
    FALSE,
    TRUE,
    o.confidence_raw,
    o.confidence_score,
    o.frp_mw,
    o.brightness_ti4,
    o.brightness_ti5,
    o.source_file,
    json_build_object(
        'firms', json_build_object(
            'satellite', o.satellite,
            'instrument', o.instrument,
            'confidence', o.confidence_raw,
            'frp_mw', o.frp_mw,
            'daynight', o.daynight,
            'attributes', o.attributes
        )
    )
FROM firms_hotspot_observations o
WHERE o.event_id = 'dixie_fire_2021'
  AND o.in_final_perimeter;

-- Review units for downstream vision and realtime workflows:
-- 10-minute time buckets and 0.02-degree cells (roughly 2 km at this latitude).
INSERT INTO fire_hotspot_clusters (
    cluster_id, event_id, observed_at, grid_x, grid_y, center_geom,
    point_count, max_frp_mw, mean_confidence, representative_candidate_id,
    candidate_ids, status, imagery_status, is_simulated, is_replay
)
SELECT
    'dixie_fire_2021-cluster-' ||
    to_char(date_bin('10 minutes', o.observed_at, TIMESTAMPTZ '2000-01-01 00:00:00+00'), 'YYYYMMDD"T"HH24MI"Z"') || '-' ||
    floor(o.longitude / 0.02)::integer || '-' ||
    floor(o.latitude / 0.02)::integer,
    o.event_id,
    date_bin('10 minutes', o.observed_at, TIMESTAMPTZ '2000-01-01 00:00:00+00'),
    floor(o.longitude / 0.02)::integer,
    floor(o.latitude / 0.02)::integer,
    ST_Centroid(ST_Collect(o.location_geom)),
    COUNT(*)::integer,
    MAX(o.frp_mw),
    AVG(o.confidence_score),
    (array_agg(o.source_record_id ORDER BY o.frp_mw DESC NULLS LAST, o.source_record_id))[1],
    jsonb_agg(o.source_record_id ORDER BY o.frp_mw DESC NULLS LAST, o.source_record_id),
    'candidate',
    'pending',
    FALSE,
    TRUE
FROM firms_hotspot_observations o
WHERE o.event_id = 'dixie_fire_2021'
  AND o.in_final_perimeter
GROUP BY
    o.event_id,
    date_bin('10 minutes', o.observed_at, TIMESTAMPTZ '2000-01-01 00:00:00+00'),
    floor(o.longitude / 0.02)::integer,
    floor(o.latitude / 0.02)::integer;

INSERT INTO fire_data_manifests (
    dataset_id, event_id, name, source_url, license, acquired_at,
    spatial_extent, temporal_extent, source_crs, target_crs,
    processing_steps, local_path
)
VALUES
(
    'dixie_fire_2021_firms_viirs_snpp_sp',
    'dixie_fire_2021',
    'Dixie Fire VIIRS S-NPP historical hotspot observations',
    'https://firms.modaps.eosdis.nasa.gov/',
    'NASA Earthdata/FIRMS',
    CURRENT_DATE,
    '{"west": -122.5, "south": 39.0, "east": -119.0, "north": 42.0}'::jsonb,
    '["2021-07-13", "2021-10-25"]'::jsonb,
    'EPSG:4326',
    'EPSG:4326',
    '["CSV header validation", "UTC time normalization", "point geometry creation", "MTBS perimeter spatial filtering"]'::jsonb,
    'data/raw/firms/'
),
(
    'dixie_fire_2021_mtbs_burn_area',
    'dixie_fire_2021',
    'Dixie Fire MTBS burned area boundary',
    'https://www.mtbs.gov/',
    'USGS/USDA Forest Service MTBS',
    CURRENT_DATE,
    '{"west": -122.5, "south": 39.0, "east": -119.0, "north": 42.0}'::jsonb,
    '["2020-07-08", "2022-07-14"]'::jsonb,
    'EPSG:5070',
    'EPSG:4326',
    '["Shapefile validation", "Albers to WGS84 transformation", "MultiPolygon geometry validation"]'::jsonb,
    'data/raw/burned_area/dixie_fire_2021_mtbs_burn_area/'
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
