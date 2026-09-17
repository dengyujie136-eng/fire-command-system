from sqlalchemy import Connection, text


SPATIAL_COLUMNS = (
    """
    ALTER TABLE fire_events
    ADD COLUMN IF NOT EXISTS ignition_geom geometry(Point, 4326)
    GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(ignition_longitude, ignition_latitude), 4326)) STORED
    """,
    """
    ALTER TABLE observations
    ADD COLUMN IF NOT EXISTS location_geom geometry(Point, 4326)
    GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)) STORED
    """,
    """
    ALTER TABLE fusion_results
    ADD COLUMN IF NOT EXISTS location_geom geometry(Point, 4326)
    GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)) STORED
    """,
    """
    ALTER TABLE trusted_fire_points
    ADD COLUMN IF NOT EXISTS location_geom geometry(Point, 4326)
    GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)) STORED
    """,
    """
    ALTER TABLE uav_assets
    ADD COLUMN IF NOT EXISTS location_geom geometry(Point, 4326)
    GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)) STORED
    """,
    """
    ALTER TABLE fire_front_steps
    ADD COLUMN IF NOT EXISTS fireline_geom geometry(Geometry, 4326)
    GENERATED ALWAYS AS (
        CASE
            WHEN fireline_geojson IS NULL OR fireline_geojson::text IN ('{}', 'null') THEN NULL
            ELSE ST_SetSRID(ST_GeomFromGeoJSON((fireline_geojson -> 'geometry')::text), 4326)
        END
    ) STORED
    """,
    """
    ALTER TABLE route_plans
    ADD COLUMN IF NOT EXISTS route_geom geometry(LineString, 4326)
    GENERATED ALWAYS AS (
        CASE
            WHEN geometry IS NULL OR geometry::text IN ('{}', 'null') THEN NULL
            ELSE ST_SetSRID(ST_GeomFromGeoJSON((geometry -> 'geojson')::text), 4326)
        END
    ) STORED
    """,
    """
    ALTER TABLE spatial_impact_records
    ADD COLUMN IF NOT EXISTS impact_geom geometry(Geometry, 4326)
    GENERATED ALWAYS AS (
        CASE
            WHEN geometry IS NULL OR geometry::text IN ('{}', 'null') THEN NULL
            ELSE ST_SetSRID(ST_GeomFromGeoJSON(geometry::text), 4326)
        END
    ) STORED
    """,
    """
    ALTER TABLE emergency_route_plans
    ADD COLUMN IF NOT EXISTS route_geom geometry(LineString, 4326)
    GENERATED ALWAYS AS (
        CASE
            WHEN geometry IS NULL OR geometry::text IN ('{}', 'null') THEN NULL
            ELSE ST_SetSRID(ST_GeomFromGeoJSON((geometry -> 'geojson')::text), 4326)
        END
    ) STORED
    """,
    """
    ALTER TABLE visual_verification_cases
    ADD COLUMN IF NOT EXISTS location_geom geometry(Point, 4326)
    GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)) STORED
    """,
    """
    ALTER TABLE fire_confirmations
    ADD COLUMN IF NOT EXISTS location_geom geometry(Point, 4326)
    GENERATED ALWAYS AS (
        CASE WHEN longitude IS NULL OR latitude IS NULL THEN NULL
        ELSE ST_SetSRID(ST_MakePoint(longitude, latitude), 4326) END
    ) STORED
    """,
    """
    ALTER TABLE imagery_catalog
    ADD COLUMN IF NOT EXISTS footprint_geom geometry(Geometry, 4326)
    GENERATED ALWAYS AS (
        CASE WHEN footprint_geojson IS NULL OR footprint_geojson::text IN ('{}', 'null') THEN NULL
        ELSE ST_SetSRID(ST_GeomFromGeoJSON(footprint_geojson::text), 4326) END
    ) STORED
    """,
    """
    ALTER TABLE visual_image_derivatives
    ADD COLUMN IF NOT EXISTS extent_geom geometry(Geometry, 4326)
    GENERATED ALWAYS AS (
        CASE WHEN extent_geojson IS NULL OR extent_geojson::text IN ('{}', 'null') THEN NULL
        ELSE ST_SetSRID(ST_GeomFromGeoJSON(extent_geojson::text), 4326) END
    ) STORED
    """,
    """
    ALTER TABLE visual_findings
    ADD COLUMN IF NOT EXISTS finding_geom geometry(Geometry, 4326)
    GENERATED ALWAYS AS (
        CASE WHEN geometry_geojson IS NULL OR geometry_geojson::text IN ('{}', 'null') THEN NULL
        ELSE ST_SetSRID(ST_GeomFromGeoJSON(geometry_geojson::text), 4326) END
    ) STORED
    """,
    """
    ALTER TABLE realtime_hotspots
    ADD COLUMN IF NOT EXISTS location_geom geometry(Point, 4326)
    GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)) STORED
    """,
)

SPATIAL_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_fire_events_ignition_geom ON fire_events USING GIST (ignition_geom)",
    "CREATE INDEX IF NOT EXISTS ix_observations_location_geom ON observations USING GIST (location_geom)",
    "CREATE INDEX IF NOT EXISTS ix_fusion_results_location_geom ON fusion_results USING GIST (location_geom)",
    "CREATE INDEX IF NOT EXISTS ix_trusted_fire_points_location_geom ON trusted_fire_points USING GIST (location_geom)",
    "CREATE INDEX IF NOT EXISTS ix_uav_assets_location_geom ON uav_assets USING GIST (location_geom)",
    "CREATE INDEX IF NOT EXISTS ix_fire_front_steps_fireline_geom ON fire_front_steps USING GIST (fireline_geom)",
    "CREATE INDEX IF NOT EXISTS ix_route_plans_route_geom ON route_plans USING GIST (route_geom)",
    "CREATE INDEX IF NOT EXISTS ix_spatial_impact_records_impact_geom ON spatial_impact_records USING GIST (impact_geom)",
    "CREATE INDEX IF NOT EXISTS ix_emergency_route_plans_route_geom ON emergency_route_plans USING GIST (route_geom)",
    "CREATE INDEX IF NOT EXISTS ix_visual_cases_location_geom ON visual_verification_cases USING GIST (location_geom)",
    "CREATE INDEX IF NOT EXISTS ix_fire_confirmations_location_geom ON fire_confirmations USING GIST (location_geom)",
    "CREATE INDEX IF NOT EXISTS ix_imagery_catalog_footprint_geom ON imagery_catalog USING GIST (footprint_geom)",
    "CREATE INDEX IF NOT EXISTS ix_visual_derivatives_extent_geom ON visual_image_derivatives USING GIST (extent_geom)",
    "CREATE INDEX IF NOT EXISTS ix_visual_findings_finding_geom ON visual_findings USING GIST (finding_geom)",
    "CREATE INDEX IF NOT EXISTS ix_realtime_hotspots_location_geom ON realtime_hotspots USING GIST (location_geom)",
)

SCALAR_SCHEMA_UPGRADES = (
    "ALTER TABLE visual_verification_cases ADD COLUMN IF NOT EXISTS source_cluster_id VARCHAR(180)",
    "ALTER TABLE visual_verification_cases ADD COLUMN IF NOT EXISTS cluster_point_count INTEGER",
    "ALTER TABLE visual_verification_cases ADD COLUMN IF NOT EXISTS cluster_mean_confidence DOUBLE PRECISION",
    "ALTER TABLE visual_verification_cases ADD COLUMN IF NOT EXISTS cluster_max_frp_mw DOUBLE PRECISION",
    "CREATE INDEX IF NOT EXISTS ix_visual_case_source_cluster ON visual_verification_cases (event_id, source_cluster_id)",
)


def install_postgis_schema(connection: Connection) -> None:
    """Add PostGIS-generated geometry columns while preserving the public JSON API."""
    if connection.dialect.name != "postgresql":
        return

    connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    for statement in SCALAR_SCHEMA_UPGRADES:
        connection.execute(text(statement))
    for statement in SPATIAL_COLUMNS:
        connection.execute(text(statement))
    for statement in SPATIAL_INDEXES:
        connection.execute(text(statement))
