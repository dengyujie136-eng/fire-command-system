from __future__ import annotations

import asyncio
import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.spread import FireFrontStep, SimulationRun
from app.schemas.spread import HistoricalCalibrationRequest, HistoricalSpreadRunRequest
from app.services.event_service import append_timeline, get_event_or_404
from app.services.spread_service import build_feature_collection
from app.services.websocket_manager import websocket_manager
from app.tools.raster_fire_spread import TOOL_NAME, TOOL_VERSION, run_raster_fire_spread


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _circular_interpolate(start: float, end: float, ratio: float) -> float:
    delta = (end - start + 180.0) % 360.0 - 180.0
    return (start + delta * ratio) % 360.0


def _interpolate_weather(rows: list[dict[str, Any]], valid_at: datetime) -> dict[str, Any]:
    before = max((row for row in rows if row["observed_at"] <= valid_at), key=lambda row: row["observed_at"])
    after = min((row for row in rows if row["observed_at"] >= valid_at), key=lambda row: row["observed_at"])
    span = (after["observed_at"] - before["observed_at"]).total_seconds()
    ratio = 0.0 if span == 0 else (valid_at - before["observed_at"]).total_seconds() / span

    def linear(name: str) -> float:
        return float(before[name]) + (float(after[name]) - float(before[name])) * ratio

    return {
        "valid_at": valid_at,
        "temperature_c": linear("temperature_c"),
        "humidity_percent": linear("humidity_percent"),
        "wind_speed_m_s": linear("wind_speed_m_s"),
        "wind_direction_deg": _circular_interpolate(
            float(before["wind_direction_deg"]),
            float(after["wind_direction_deg"]),
            ratio,
        ),
        "precipitation_mm_h": linear("precipitation_mm"),
    }


def _equilibrium_moisture_fraction(temperature_c: float, humidity_percent: float) -> float:
    humidity = max(0.0, min(100.0, humidity_percent))
    if humidity < 10:
        percent = 0.03229 + 0.281073 * humidity - 0.000578 * humidity * temperature_c
    elif humidity <= 50:
        percent = 2.22749 + 0.160107 * humidity - 0.01478 * temperature_c
    else:
        percent = (
            21.0606
            + 0.005565 * humidity * humidity
            - 0.00035 * humidity * temperature_c
            - 0.483199 * humidity
        )
    return max(0.03, min(0.35, percent / 100.0))


def _weather_index_proxy(weather: dict[str, Any]) -> float:
    temperature = weather["temperature_c"]
    humidity = weather["humidity_percent"]
    wind = weather["wind_speed_m_s"]
    rain = weather["precipitation_mm_h"]
    raw = (temperature - 10.0) * 0.45 + (40.0 - humidity) * 0.35 + wind * 1.8 - rain * 8.0
    return max(0.0, min(45.0, raw))


async def _weather_timeline(
    db: AsyncSession,
    event_id: str,
    start_at: datetime,
    end_at: datetime,
) -> list[dict[str, Any]]:
    result = await db.execute(
        text(
            """
            SELECT observed_at, temperature_c,
                   relative_humidity_percent AS humidity_percent,
                   wind_speed_m_s, wind_direction_deg,
                   COALESCE(precipitation_mm, 0) AS precipitation_mm
            FROM weather_hourly_observations
            WHERE event_id = :event_id
              AND observed_at >= :query_start
              AND observed_at <= :query_end
            ORDER BY observed_at
            """
        ),
        {
            "event_id": event_id,
            "query_start": start_at - timedelta(hours=1),
            "query_end": end_at + timedelta(hours=1),
        },
    )
    rows = []
    for row in result.mappings().all():
        item = dict(row)
        item["observed_at"] = _utc(item["observed_at"])
        rows.append(item)
    if not rows or rows[0]["observed_at"] > start_at or rows[-1]["observed_at"] < end_at:
        raise AppError(
            "Hourly weather does not cover the requested historical interval.",
            code="historical_weather_gap",
            status_code=400,
        )
    valid_times = [start_at]
    cursor = start_at.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    while cursor < end_at:
        valid_times.append(cursor)
        cursor += timedelta(hours=1)
    valid_times.append(end_at)

    timeline = []
    previous_moisture: float | None = None
    for valid_at in valid_times:
        weather = _interpolate_weather(rows, valid_at)
        equilibrium = _equilibrium_moisture_fraction(
            weather["temperature_c"],
            weather["humidity_percent"],
        )
        # A one-hour time-lag fuel approaches equilibrium gradually. Rain is
        # retained as a separate rate-reduction input.
        fuel_moisture = equilibrium if previous_moisture is None else previous_moisture + 0.63 * (equilibrium - previous_moisture)
        previous_moisture = fuel_moisture
        timeline.append(
            {
                "elapsed_minutes": round((valid_at - start_at).total_seconds() / 60.0),
                "valid_at": valid_at.isoformat().replace("+00:00", "Z"),
                "temperature_c": weather["temperature_c"],
                "humidity_percent": weather["humidity_percent"],
                "wind_speed_m_s": weather["wind_speed_m_s"],
                "wind_direction_deg": weather["wind_direction_deg"],
                "fuel_moisture": fuel_moisture,
                "fire_weather_index": _weather_index_proxy(weather),
                "precipitation_mm_h": weather["precipitation_mm_h"],
                "source": "NASA_POWER_hourly+equilibrium_moisture+weather_index_proxy",
            }
        )
    return timeline


async def _comparison_metrics(
    db: AsyncSession,
    event_id: str,
    start_at: datetime,
    end_at: datetime,
    longitude: float,
    latitude: float,
    radius_km: float,
    simulated_area_km2: float,
    simulated_geometry: dict[str, Any],
) -> dict[str, Any]:
    result = await db.execute(
        text(
            """
            WITH ignition AS (
              SELECT ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326) AS geom
            ), nearby AS (
              SELECT location_geom
              FROM fire_hotspots, ignition
              WHERE event_id = :event_id
                AND observed_at >= :start_at
                AND observed_at <= :end_at
                AND ST_DWithin(
                  location_geom::geography,
                  ignition.geom::geography,
                  :radius_m
                )
            ), hotspot_hull AS (
              SELECT ST_ConvexHull(ST_Collect(location_geom)) AS geom
              FROM nearby
            ), simulated AS (
              SELECT ST_MakeValid(
                ST_SetSRID(ST_GeomFromGeoJSON(:simulated_geometry), 4326)
              ) AS geom
            ), overlap AS (
              SELECT
                ST_Area(ST_Intersection(h.geom, s.geom)::geography) / 1000000.0 AS intersection_km2,
                ST_Area(ST_Union(h.geom, s.geom)::geography) / 1000000.0 AS union_km2
              FROM hotspot_hull h, simulated s
              WHERE h.geom IS NOT NULL AND NOT ST_IsEmpty(h.geom)
            )
            SELECT
              (SELECT COUNT(*) FROM nearby) AS hotspot_count,
              COALESCE(
                (SELECT ST_Area(geom::geography) / 1000000.0 FROM hotspot_hull),
                0
              ) AS hotspot_hull_km2,
              COALESCE((SELECT intersection_km2 FROM overlap), 0) AS intersection_km2,
              COALESCE((SELECT union_km2 FROM overlap), 0) AS union_km2
            """
        ),
        {
            "event_id": event_id,
            "start_at": start_at,
            "end_at": end_at,
            "longitude": longitude,
            "latitude": latitude,
            "radius_m": radius_km * 1000.0,
            "simulated_geometry": json.dumps(simulated_geometry),
        },
    )
    row = dict(result.mappings().one())
    hotspot_hull = float(row["hotspot_hull_km2"] or 0)
    intersection = float(row["intersection_km2"] or 0)
    union = float(row["union_km2"] or 0)
    return {
        "comparison_type": "time_matched_FIRMS_convex_hull_proxy",
        "hotspot_search_radius_km": radius_km,
        "nearby_hotspot_count": int(row["hotspot_count"] or 0),
        "nearby_hotspot_hull_km2": round(hotspot_hull, 4),
        "intersection_with_hotspot_hull_km2": round(intersection, 4),
        "spatial_iou_percent": round(intersection / union * 100.0, 2) if union > 0 else None,
        "simulation_precision_percent": (
            round(intersection / simulated_area_km2 * 100.0, 2) if simulated_area_km2 > 0 else None
        ),
        "hotspot_hull_recall_percent": (
            round(intersection / hotspot_hull * 100.0, 2) if hotspot_hull > 0 else None
        ),
        "area_bias_vs_hotspot_hull_percent": (
            round((simulated_area_km2 / hotspot_hull - 1.0) * 100.0, 2) if hotspot_hull > 0 else None
        ),
        "warning": (
            "The FIRMS convex hull is a time-matched active-fire observation proxy, "
            "not a measured burned-area perimeter."
        ),
    }


async def _temporal_comparison_metrics(
    db: AsyncSession,
    event_id: str,
    start_at: datetime,
    longitude: float,
    latitude: float,
    radius_km: float,
    steps: list[FireFrontStep],
) -> list[dict[str, Any]]:
    """Compare every simulated checkpoint with its nearby FIRMS time window."""
    metrics: list[dict[str, Any]] = []
    for step in steps:
        observed_at = start_at + timedelta(minutes=step.time_minute)
        window_start = observed_at - timedelta(minutes=30)
        window_end = observed_at + timedelta(minutes=30)
        result = await db.execute(
            text(
                """
                WITH ignition AS (
                  SELECT ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326) AS geom
                ), cumulative_nearby AS (
                  SELECT location_geom
                  FROM fire_hotspots, ignition
                  WHERE event_id = :event_id
                    AND observed_at >= :simulation_start
                    AND observed_at <= :observed_at
                    AND ST_DWithin(
                      location_geom::geography,
                      ignition.geom::geography,
                      :radius_m
                    )
                ), recent_nearby AS (
                  SELECT location_geom
                  FROM fire_hotspots, ignition
                  WHERE event_id = :event_id
                    AND observed_at >= :window_start
                    AND observed_at <= :window_end
                    AND ST_DWithin(
                      location_geom::geography,
                      ignition.geom::geography,
                      :radius_m
                    )
                ), hotspot_hull AS (
                  SELECT ST_ConvexHull(ST_Collect(location_geom)) AS geom
                  FROM cumulative_nearby
                ), recent_centroid AS (
                  SELECT ST_Centroid(ST_Collect(location_geom)) AS geom
                  FROM recent_nearby
                ), simulated AS (
                  SELECT ST_MakeValid(
                    ST_SetSRID(ST_GeomFromGeoJSON(:simulated_geometry), 4326)
                  ) AS geom
                ), overlap AS (
                  SELECT
                    ST_Area(ST_Intersection(h.geom, s.geom)::geography) / 1000000.0 AS intersection_km2,
                    ST_Area(ST_Union(h.geom, s.geom)::geography) / 1000000.0 AS union_km2,
                    CASE WHEN ST_Dimension(h.geom) = 2 THEN
                      ST_HausdorffDistance(ST_Transform(h.geom, 32610), ST_Transform(s.geom, 32610)) / 1000.0
                    END AS hausdorff_km
                  FROM hotspot_hull h, simulated s
                  WHERE h.geom IS NOT NULL AND NOT ST_IsEmpty(h.geom)
                )
                SELECT
                  (SELECT COUNT(*) FROM cumulative_nearby) AS cumulative_hotspot_count,
                  (SELECT COUNT(*) FROM recent_nearby) AS recent_hotspot_count,
                  COALESCE((SELECT ST_Area(geom::geography) / 1000000.0 FROM hotspot_hull), 0) AS hotspot_hull_km2,
                  COALESCE((SELECT intersection_km2 FROM overlap), 0) AS intersection_km2,
                  COALESCE((SELECT union_km2 FROM overlap), 0) AS union_km2,
                  (SELECT hausdorff_km FROM overlap) AS hausdorff_km,
                  (SELECT MAX(ST_Distance(location_geom::geography, ignition.geom::geography)) / 1000.0
                   FROM cumulative_nearby, ignition) AS hotspot_max_radius_km,
                  ST_X((SELECT geom FROM recent_centroid)) AS hotspot_centroid_longitude,
                  ST_Y((SELECT geom FROM recent_centroid)) AS hotspot_centroid_latitude
                """
            ),
            {
                "event_id": event_id,
                "simulation_start": start_at,
                "observed_at": observed_at,
                "window_start": window_start,
                "window_end": window_end,
                "longitude": longitude,
                "latitude": latitude,
                "radius_m": radius_km * 1000.0,
                "simulated_geometry": json.dumps(step.fireline_geojson["geometry"]),
            },
        )
        row = dict(result.mappings().one())
        hotspot_hull = float(row["hotspot_hull_km2"] or 0)
        intersection = float(row["intersection_km2"] or 0)
        union = float(row["union_km2"] or 0)
        simulated_area = float(step.area_km2 or 0)
        hotspot_lon = row.get("hotspot_centroid_longitude")
        hotspot_lat = row.get("hotspot_centroid_latitude")
        hotspot_max_radius = row.get("hotspot_max_radius_km")
        area_metrics_available = hotspot_hull > 0
        direction_error = None
        hotspot_direction = None
        if hotspot_lon is not None and hotspot_lat is not None:
            hotspot_direction = math.degrees(
                math.atan2(
                    (float(hotspot_lon) - longitude) * math.cos(math.radians(latitude)),
                    float(hotspot_lat) - latitude,
                )
            ) % 360.0
            direction_error = abs(
                (float(step.spread_direction_deg) - hotspot_direction + 180.0) % 360.0 - 180.0
            )
        metrics.append(
            {
                "time_minute": step.time_minute,
                "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
                "firms_window_start": window_start.isoformat().replace("+00:00", "Z"),
                "firms_window_end": window_end.isoformat().replace("+00:00", "Z"),
                "hotspot_count": int(row["cumulative_hotspot_count"] or 0),
                "cumulative_hotspot_count": int(row["cumulative_hotspot_count"] or 0),
                "recent_hotspot_count": int(row["recent_hotspot_count"] or 0),
                "simulated_area_km2": round(simulated_area, 4),
                "hotspot_hull_km2": round(hotspot_hull, 4),
                "intersection_km2": round(intersection, 4),
                "area_error_km2": round(simulated_area - hotspot_hull, 4) if area_metrics_available else None,
                "area_error_percent": round((simulated_area / hotspot_hull - 1.0) * 100.0, 2) if area_metrics_available else None,
                "spatial_iou_percent": round(intersection / union * 100.0, 2) if area_metrics_available and union > 0 else None,
                "simulation_precision_percent": round(intersection / simulated_area * 100.0, 2) if area_metrics_available and simulated_area > 0 else None,
                "hotspot_hull_recall_percent": round(intersection / hotspot_hull * 100.0, 2) if area_metrics_available else None,
                "hausdorff_distance_km": round(float(row["hausdorff_km"]), 3) if row.get("hausdorff_km") is not None else None,
                "simulated_max_radius_km": round(float(step.radius_km), 4),
                "firms_max_radius_km": round(float(hotspot_max_radius), 4) if hotspot_max_radius is not None else None,
                "max_radius_error_km": round(float(step.radius_km) - float(hotspot_max_radius), 4) if hotspot_max_radius is not None else None,
                "simulated_spread_direction_deg": round(float(step.spread_direction_deg), 1),
                "firms_centroid_direction_deg": round(hotspot_direction, 1) if hotspot_direction is not None else None,
                "direction_error_deg": round(direction_error, 1) if direction_error is not None else None,
            }
        )
    return metrics


def _summarize_temporal_validation(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    def values(name: str) -> list[float]:
        return [float(item[name]) for item in metrics if item.get(name) is not None]

    def mean(name: str) -> float | None:
        available = values(name)
        return round(sum(available) / len(available), 3) if available else None

    return {
        "checkpoint_count": len(metrics),
        "checkpoints_with_hotspots": sum(item["cumulative_hotspot_count"] > 0 for item in metrics),
        "checkpoints_with_area_metrics": len(values("spatial_iou_percent")),
        "mean_spatial_iou_percent": mean("spatial_iou_percent"),
        "mean_absolute_area_error_km2": (
            round(sum(abs(value) for value in values("area_error_km2")) / len(values("area_error_km2")), 3)
            if values("area_error_km2")
            else None
        ),
        "mean_hausdorff_distance_km": mean("hausdorff_distance_km"),
        "mean_direction_error_deg": mean("direction_error_deg"),
        "mean_absolute_max_radius_error_km": (
            round(sum(abs(value) for value in values("max_radius_error_km")) / len(values("max_radius_error_km")), 3)
            if values("max_radius_error_km")
            else None
        ),
    }


async def create_historical_spread_run(
    db: AsyncSession,
    event_id: str,
    request: HistoricalSpreadRunRequest,
    calibration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = await get_event_or_404(db, event_id)
    start_at = _utc(request.start_at or event.started_at)
    end_at = start_at + timedelta(hours=request.horizon_hours)
    timeline = await _weather_timeline(db, event_id, start_at, end_at)
    dem_path = "processed/dem/dixie_fire_2021_copernicus_dem_30m_utm10.tif"
    landcover_path = "processed/fuel/dixie_fire_2021_worldcover_30m_utm10.tif"
    try:
        tool_result = await asyncio.to_thread(
            run_raster_fire_spread,
            ignition_longitude=event.ignition_longitude,
            ignition_latitude=event.ignition_latitude,
            environment_timeline=timeline,
            dem_path=dem_path,
            landcover_path=landcover_path,
            raster_resolution_m=request.raster_resolution_m,
            simulation_buffer_km=request.simulation_buffer_km,
            initial_radius_m=request.initial_radius_m,
            suppression_factor=request.suppression_factor,
            wind_direction_convention=request.wind_direction_convention,
            spread_rate_multiplier=request.spread_rate_multiplier,
            wind_influence_multiplier=request.wind_influence_multiplier,
            terrain_influence_multiplier=request.terrain_influence_multiplier,
        )
    except (OSError, TypeError, ValueError) as exc:
        raise AppError(
            f"Historical raster spread tool rejected its input: {exc}",
            code="historical_raster_spread_failed",
            status_code=400,
        ) from exc

    run_id = f"spr_{uuid4().hex[:18]}"
    steps = []
    for index, item in enumerate(tool_result["steps"]):
        feature = item["fireline_geojson"]
        used_frame = tool_result["input"]["environment_timeline"][index - 1] if index else None
        used_from = (
            start_at + timedelta(minutes=tool_result["steps"][index - 1]["elapsed_minutes"])
            if index
            else None
        )
        used_to = start_at + timedelta(minutes=item["elapsed_minutes"]) if index else None
        feature["properties"].update(
            {
                "run_id": run_id,
                "event_id": event_id,
                "time_minute": item["elapsed_minutes"],
                "run_mode": "historical_replay",
                "initial_fireline_source": "historical_candidate_hotspot",
                "weather_used": used_frame,
                "weather_used_from": used_from.isoformat().replace("+00:00", "Z") if used_from else None,
                "weather_used_to": used_to.isoformat().replace("+00:00", "Z") if used_to else None,
            }
        )
        steps.append(
            FireFrontStep(
                step_id=f"ffs_{uuid4().hex}",
                run_id=run_id,
                event_id=event_id,
                time_minute=item["elapsed_minutes"],
                elapsed_seconds=item["elapsed_seconds"],
                area_km2=item["area_km2"],
                radius_km=item["radius_km"],
                spread_direction_deg=item["spread_direction_deg"],
                fireline_geojson=feature,
            )
        )
    final = steps[-1]
    comparison = await _comparison_metrics(
        db,
        event_id,
        start_at,
        end_at,
        event.ignition_longitude,
        event.ignition_latitude,
        request.hotspot_comparison_radius_km,
        final.area_km2,
        final.fireline_geojson["geometry"],
    )
    temporal_validation = await _temporal_comparison_metrics(
        db,
        event_id,
        start_at,
        event.ignition_longitude,
        event.ignition_latitude,
        request.hotspot_comparison_radius_km,
        steps,
    )
    temporal_validation_summary = _summarize_temporal_validation(temporal_validation)
    max_fwi = max(frame["fire_weather_index"] for frame in timeline)
    risk_level = "high" if final.area_km2 >= 4.5 or max_fwi >= 24 else "medium" if final.area_km2 >= 1.2 else "low"
    summary = {
        **tool_result["summary"],
        "historical_event_id": event_id,
        "historical_start_at": start_at.isoformat().replace("+00:00", "Z"),
        "historical_end_at": end_at.isoformat().replace("+00:00", "Z"),
        "environment_source": "database_hourly_weather",
        "weather_data_quality": {
            "source": "NASA_POWER_hourly",
            "frame_count": len(timeline),
            "temporal_resolution_minutes": 60,
            "spatial_mode": "regional_representative_field",
            "is_spatially_observed": False,
            "boundary_frames_interpolated": True,
            "used_for": ["fireline_spread_rate", "wind_direction", "fireline_intensity"],
        },
        "fuel_moisture_method": "one_hour_equilibrium_moisture_time_lag_proxy",
        "fire_weather_index_method": "documented_weather_index_proxy_not_official_FWI",
        "comparison": comparison,
        "calibration": calibration,
        "temporal_validation": temporal_validation,
        "temporal_validation_summary": temporal_validation_summary,
        "temporal_validation_method": "FIRMS_time_window_plus_convex_hull_per_checkpoint",
        "usable_by_agent": True,
        "model_validation_status": (
            "calibrated_to_single_dixie_window" if calibration else "course_demo_uncalibrated"
        ),
    }
    run = SimulationRun(
        run_id=run_id,
        event_id=event_id,
        scenario_id=event.scenario_id,
        status="completed",
        engine="raster_agent_tool",
        forefire_attempted=False,
        forefire_available=False,
        fallback_used=False,
        start_minute=0,
        horizon_minutes=request.horizon_hours * 60,
        step_minutes=60,
        ignition_longitude=event.ignition_longitude,
        ignition_latitude=event.ignition_latitude,
        final_area_km2=final.area_km2,
        max_radius_km=max(step.radius_km for step in steps),
        spread_direction_deg=final.spread_direction_deg,
        risk_level=risk_level,
        input_snapshot={
            "event_id": event_id,
            "ignition_point": {
                "longitude": event.ignition_longitude,
                "latitude": event.ignition_latitude,
                "confidence": event.ignition_confidence,
                "input_source": "historical_candidate_hotspot",
            },
            "environment_timeline": tool_result["input"]["environment_timeline"],
            "environment_source": "database_hourly_weather",
            "weather_data_quality": summary["weather_data_quality"],
            "raster_inputs": {"dem_path": dem_path, "landcover_path": landcover_path},
            "raster_resolution_m": request.raster_resolution_m,
            "simulation_buffer_km": request.simulation_buffer_km,
            "model_parameters": tool_result["input"]["model_parameters"],
            "wind_direction_convention": request.wind_direction_convention,
            "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
        },
        result_summary=summary,
        error_message="",
    )
    db.add(run)
    await db.flush()
    for step in steps:
        db.add(step)
    await append_timeline(
        db,
        event_id=event_id,
        event_type="spread.historical.completed",
        status=event.status,
        title="Historical raster spread replay completed",
        message="Hourly weather, projected DEM, and WorldCover produced a grid fire perimeter.",
        payload={
            "run_id": run_id,
            "engine": run.engine,
            "final_area_km2": final.area_km2,
            "comparison": comparison,
        },
        broadcast=True,
    )
    await db.commit()
    await db.refresh(run)
    for step in steps:
        await db.refresh(step)
    geojson = build_feature_collection(steps)
    await websocket_manager.broadcast_event(
        event_id,
        "spread.historical.completed",
        {"run_id": run_id, "engine": run.engine, "geojson": geojson, "summary": summary},
    )
    return {"run": run, "steps": steps, "geojson": geojson}


def _calibration_score(comparison: dict[str, Any]) -> float:
    iou = comparison.get("spatial_iou_percent")
    hull_area = float(comparison.get("nearby_hotspot_hull_km2") or 0)
    simulated_area = float(comparison.get("simulated_area_km2") or 0)
    if iou is None or hull_area <= 0 or simulated_area <= 0:
        return -1.0
    area_similarity = math.exp(-abs(math.log(simulated_area / hull_area)))
    return round(0.75 * float(iou) / 100.0 + 0.25 * area_similarity, 6)


async def calibrate_historical_spread_run(
    db: AsyncSession,
    event_id: str,
    request: HistoricalCalibrationRequest,
) -> dict[str, Any]:
    event = await get_event_or_404(db, event_id)
    start_at = _utc(request.start_at or event.started_at)
    end_at = start_at + timedelta(hours=request.horizon_hours)
    timeline = await _weather_timeline(db, event_id, start_at, end_at)
    calibration_hours = (6, 12, 24)
    dem_path = "processed/dem/dixie_fire_2021_copernicus_dem_30m_utm10.tif"
    landcover_path = "processed/fuel/dixie_fire_2021_worldcover_30m_utm10.tif"

    results: list[dict[str, Any]] = []

    async def evaluate(
        name: str,
        spread_rate: float,
        wind_influence: float,
        terrain_influence: float,
    ) -> dict[str, Any]:
        tool_result = await asyncio.to_thread(
            run_raster_fire_spread,
            ignition_longitude=event.ignition_longitude,
            ignition_latitude=event.ignition_latitude,
            environment_timeline=timeline,
            dem_path=dem_path,
            landcover_path=landcover_path,
            raster_resolution_m=request.raster_resolution_m,
            simulation_buffer_km=request.simulation_buffer_km,
            initial_radius_m=request.initial_radius_m,
            suppression_factor=request.suppression_factor,
            wind_direction_convention=request.wind_direction_convention,
            spread_rate_multiplier=spread_rate,
            wind_influence_multiplier=wind_influence,
            terrain_influence_multiplier=terrain_influence,
            checkpoint_minutes=[hours * 60 for hours in calibration_hours],
        )
        window_metrics = []
        for hours in calibration_hours:
            step = next(
                item for item in tool_result["steps"]
                if item["elapsed_minutes"] == hours * 60
            )
            comparison = await _comparison_metrics(
                db,
                event_id,
                start_at,
                start_at + timedelta(hours=hours),
                event.ignition_longitude,
                event.ignition_latitude,
                request.hotspot_comparison_radius_km,
                step["area_km2"],
                step["fireline_geojson"]["geometry"],
            )
            comparison["simulated_area_km2"] = step["area_km2"]
            window_metrics.append(
                {
                    "horizon_hours": hours,
                    "score": _calibration_score(comparison),
                    **comparison,
                }
            )
        valid_scores = [item["score"] for item in window_metrics if item["score"] >= 0]
        mean_score = sum(valid_scores) / len(valid_scores) if valid_scores else -1.0
        worst_score = min(valid_scores, default=-1.0)
        candidate = {
            "name": name,
            "parameters": tool_result["input"]["model_parameters"],
            "score": round(0.7 * mean_score + 0.3 * worst_score, 6) if valid_scores else -1.0,
            "mean_window_score": round(mean_score, 6),
            "worst_window_score": round(worst_score, 6),
            "metrics": window_metrics[-1],
            "window_metrics": window_metrics,
        }
        results.append(candidate)
        return candidate

    await evaluate("baseline", 1.0, 1.0, 1.0)
    await evaluate("minimum_spread", 0.6, 1.0, 1.0)
    await evaluate("slower_spread", 0.8, 1.0, 1.0)
    await evaluate("faster_spread", 1.2, 1.0, 1.0)
    stage_best = max(results, key=lambda item: item["score"])["parameters"]
    await evaluate("weaker_wind", stage_best["spread_rate_multiplier"], 0.75, 1.0)
    await evaluate("stronger_wind", stage_best["spread_rate_multiplier"], 1.25, 1.0)
    stage_best = max(results, key=lambda item: item["score"])["parameters"]
    await evaluate(
        "weaker_terrain",
        stage_best["spread_rate_multiplier"],
        stage_best["wind_influence_multiplier"],
        0.75,
    )
    await evaluate(
        "stronger_terrain",
        stage_best["spread_rate_multiplier"],
        stage_best["wind_influence_multiplier"],
        1.25,
    )
    if all(item["score"] < 0 for item in results):
        raise AppError(
            "FIRMS observations do not form a valid comparison hull in this window.",
            code="firms_calibration_unavailable",
            status_code=400,
        )
    best = max(results, key=lambda item: item["score"])
    baseline = results[0]
    calibration = {
        "status": "calibrated_to_dixie_6h_12h_24h_windows",
        "objective": (
            "Per window: 0.75 * FIRMS hull IoU + 0.25 * exponential area similarity; "
            "selection: 0.70 * three-window mean + 0.30 * worst-window score"
        ),
        "search_method": "three_stage_bounded_coordinate_search",
        "observation_proxy": "time-matched cumulative FIRMS hotspot convex hull",
        "warning": "Multi-window fit on one Dixie incident; not an independent or general wildfire validation.",
        "calibration_windows_hours": list(calibration_hours),
        "window_start": start_at.isoformat().replace("+00:00", "Z"),
        "window_end": end_at.isoformat().replace("+00:00", "Z"),
        "baseline": baseline,
        "selected": best,
        "candidates": results,
        "score_improvement": round(best["score"] - baseline["score"], 6),
    }
    selected = request.model_copy(update=best["parameters"])
    return await create_historical_spread_run(db, event_id, selected, calibration=calibration)
