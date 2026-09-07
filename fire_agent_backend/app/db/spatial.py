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
)

SPATIAL_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_fire_events_ignition_geom ON fire_events USING GIST (ignition_geom)",
    "CREATE INDEX IF NOT EXISTS ix_observations_location_geom ON observations USING GIST (location_geom)",
    "CREATE INDEX IF NOT EXISTS ix_fusion_results_location_geom ON fusion_results USING GIST (location_geom)",
    "CREATE INDEX IF NOT EXISTS ix_trusted_fire_points_location_geom ON trusted_fire_points USING GIST (location_geom)",
    "CREATE INDEX IF NOT EXISTS ix_uav_assets_location_geom ON uav_assets USING GIST (location_geom)",
    "CREATE INDEX IF NOT EXISTS ix_fire_front_steps_fireline_geom ON fire_front_steps USING GIST (fireline_geom)",
    "CREATE INDEX IF NOT EXISTS ix_route_plans_route_geom ON route_plans USING GIST (route_geom)",
)


def install_postgis_schema(connection: Connection) -> None:
    """Add PostGIS-generated geometry columns while preserving the public JSON API."""
    if connection.dialect.name != "postgresql":
        return

    connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    for statement in SPATIAL_COLUMNS:
        connection.execute(text(statement))
    for statement in SPATIAL_INDEXES:
        connection.execute(text(statement))
