from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db


router = APIRouter(prefix="/data", tags=["fire-data"])


async def _event_exists(db: AsyncSession, event_id: str) -> bool:
    result = await db.execute(
        text("SELECT 1 FROM fire_events WHERE event_id = :event_id"),
        {"event_id": event_id},
    )
    return result.scalar_one_or_none() is not None


def _json_value(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value


@router.get("/events/{event_id}")
async def fire_event_data(event_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    result = await db.execute(
        text(
            """
            SELECT event_id, name, status, scenario_id, source_mode,
                   ignition_longitude, ignition_latitude, ignition_confidence,
                   started_at, closed_at, metadata_json
            FROM fire_events
            WHERE event_id = :event_id
            """
        ),
        {"event_id": event_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Fire event not found: {event_id}")
    item = dict(row)
    metadata = _json_value(item.pop("metadata_json", None), {})
    item["metadata"] = metadata
    item["ignition_point"] = {
        "longitude": item.pop("ignition_longitude"),
        "latitude": item.pop("ignition_latitude"),
        "confidence": item.pop("ignition_confidence"),
        "crs": "EPSG:4326",
    }
    return {"schema_version": "fire.event.v0.1", "data": item}


@router.get("/events/{event_id}/hotspots")
async def list_fire_hotspots(
    event_id: str,
    status: str | None = Query(default=None),
    aggregate: bool = Query(default=False),
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if not await _event_exists(db, event_id):
        raise HTTPException(status_code=404, detail=f"Fire event not found: {event_id}")

    table = "fire_hotspot_clusters" if aggregate else "fire_hotspots"
    conditions = ["event_id = :event_id"]
    params: dict[str, Any] = {"event_id": event_id, "limit": limit, "offset": offset}
    if status:
        conditions.append("status = :status")
        params["status"] = status
    if start_at:
        conditions.append("observed_at >= :start_at")
        params["start_at"] = start_at
    if end_at:
        conditions.append("observed_at <= :end_at")
        params["end_at"] = end_at
    where = " AND ".join(conditions)

    count_result = await db.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {where}"), params)
    total = int(count_result.scalar_one())

    if aggregate:
        query = text(
            f"""
            SELECT cluster_id, event_id, observed_at,
                   ST_X(center_geom) AS longitude,
                   ST_Y(center_geom) AS latitude,
                   point_count, max_frp_mw, mean_confidence,
                   representative_candidate_id, candidate_ids,
                   status, imagery_status, is_simulated, is_replay
            FROM {table}
            WHERE {where}
            ORDER BY observed_at, cluster_id
            LIMIT :limit OFFSET :offset
            """
        )
    else:
        query = text(
            f"""
            SELECT candidate_id, event_id, observed_at,
                   ST_X(location_geom) AS longitude,
                   ST_Y(location_geom) AS latitude,
                   status, data_owner, source_product,
                   imagery_status, imagery_refs,
                   is_simulated, is_replay,
                   confidence_raw, confidence_score,
                   frp_mw, brightness_ti4, brightness_ti5,
                   source_file, product_fields
            FROM {table}
            WHERE {where}
            ORDER BY observed_at, candidate_id
            LIMIT :limit OFFSET :offset
            """
        )

    result = await db.execute(query, params)
    items = []
    for row in result.mappings().all():
        item = dict(row)
        if aggregate:
            item["candidate_ids"] = _json_value(item.get("candidate_ids"), [])
            item["center"] = {
                "longitude": item.pop("longitude"),
                "latitude": item.pop("latitude"),
                "crs": "EPSG:4326",
            }
        else:
            item["imagery_refs"] = _json_value(item.get("imagery_refs"), [])
            item["product_fields"] = _json_value(item.get("product_fields"), {})
            item["location"] = {
                "longitude": item.pop("longitude"),
                "latitude": item.pop("latitude"),
                "crs": "EPSG:4326",
            }
            item["replay"] = {"is_replay": item.pop("is_replay")}
        items.append(item)

    return {
        "schema_version": "fire.hotspot.cluster.v0.1" if aggregate else "fire.hotspot.candidate.v0.1",
        "event_id": event_id,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "aggregate": aggregate,
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@router.get("/events/{event_id}/burned-area")
async def burned_area_data(
    event_id: str,
    include_geometry: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if not await _event_exists(db, event_id):
        raise HTTPException(status_code=404, detail=f"Fire event not found: {event_id}")
    geometry_sql = ", ST_AsGeoJSON(geom)::json AS geometry" if include_geometry else ""
    result = await db.execute(
        text(
            f"""
            SELECT source_dataset, source_event_id, source_name,
                   assessment_date, area_acres, area_m2,
                   source_crs, source_file, metadata{geometry_sql}
            FROM burned_areas
            WHERE event_id = :event_id
            ORDER BY id
            LIMIT 1
            """
        ),
        {"event_id": event_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Burned area not found: {event_id}")
    item = dict(row)
    item["metadata"] = _json_value(item.get("metadata"), {})
    return {"schema_version": "fire.burned-area.v0.1", "event_id": event_id, "data": item}


@router.get("/events/{event_id}/weather")
async def list_weather_observations(
    event_id: str,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if not await _event_exists(db, event_id):
        raise HTTPException(status_code=404, detail=f"Fire event not found: {event_id}")

    conditions = ["event_id = :event_id"]
    params: dict[str, Any] = {"event_id": event_id, "limit": limit, "offset": offset}
    if start_date:
        conditions.append("observed_on >= :start_date")
        params["start_date"] = start_date
    if end_date:
        conditions.append("observed_on <= :end_date")
        params["end_date"] = end_date
    where = " AND ".join(conditions)

    count_result = await db.execute(text(f"SELECT COUNT(*) FROM weather_observations WHERE {where}"), params)
    total = int(count_result.scalar_one())
    result = await db.execute(
        text(
            f"""
            SELECT observed_on, longitude, latitude, elevation_m,
                   temperature_c, temperature_max_c, temperature_min_c,
                   relative_humidity_percent, wind_speed_m_s, wind_direction_deg,
                   precipitation_mm, solar_radiation_kwh_m2_day,
                   source_dataset, source_file, attributes
            FROM weather_observations
            WHERE {where}
            ORDER BY observed_on
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    )
    items = []
    for row in result.mappings().all():
        item = dict(row)
        item["location"] = {
            "longitude": item.pop("longitude"),
            "latitude": item.pop("latitude"),
            "crs": "EPSG:4326",
        }
        item["attributes"] = _json_value(item.get("attributes"), {})
        items.append(item)
    return {
        "schema_version": "fire.weather.daily.v0.1",
        "event_id": event_id,
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@router.get("/events/{event_id}/weather-hourly")
async def list_hourly_weather_observations(
    event_id: str,
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if not await _event_exists(db, event_id):
        raise HTTPException(status_code=404, detail=f"Fire event not found: {event_id}")

    conditions = ["event_id = :event_id"]
    params: dict[str, Any] = {"event_id": event_id, "limit": limit, "offset": offset}
    if start_at:
        conditions.append("observed_at >= :start_at")
        params["start_at"] = start_at
    if end_at:
        conditions.append("observed_at <= :end_at")
        params["end_at"] = end_at
    where = " AND ".join(conditions)

    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM weather_hourly_observations WHERE {where}"), params
    )
    total = int(count_result.scalar_one())
    result = await db.execute(
        text(
            f"""
            SELECT observed_at, observed_on, longitude, latitude, elevation_m,
                   temperature_c, relative_humidity_percent, wind_speed_m_s,
                   wind_direction_deg, wind_u_m_s, wind_v_m_s, precipitation_mm,
                   solar_radiation_mj_m2_h, is_interpolated, source_dataset,
                   source_file, attributes
            FROM weather_hourly_observations
            WHERE {where}
            ORDER BY observed_at
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    )
    items = []
    for row in result.mappings().all():
        item = dict(row)
        item["observed_at"] = item["observed_at"].isoformat().replace("+00:00", "Z")
        item["location"] = {
            "longitude": item.pop("longitude"),
            "latitude": item.pop("latitude"),
            "crs": "EPSG:4326",
        }
        item["attributes"] = _json_value(item.get("attributes"), {})
        items.append(item)
    return {
        "schema_version": "fire.weather.hourly.v0.1",
        "event_id": event_id,
        "interval_minutes": 60,
        "is_interpolated": False,
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@router.get("/events/{event_id}/realtime-replay")
async def list_realtime_replay(
    event_id: str,
    start_at: datetime,
    end_at: datetime,
    limit: int = Query(default=1000, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if not await _event_exists(db, event_id):
        raise HTTPException(status_code=404, detail=f"Fire event not found: {event_id}")
    if end_at < start_at:
        raise HTTPException(status_code=422, detail="end_at must be greater than or equal to start_at")

    params: dict[str, Any] = {
        "event_id": event_id,
        "start_at": start_at,
        "end_at": end_at,
        "limit": limit,
        "offset": offset,
    }
    where = "event_id = :event_id AND observed_at >= :start_at AND observed_at <= :end_at"
    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM fire_hotspot_clusters WHERE {where}"), params
    )
    total = int(count_result.scalar_one())
    result = await db.execute(
        text(
            f"""
            SELECT cluster_id, observed_at, ST_X(center_geom) AS longitude,
                   ST_Y(center_geom) AS latitude, point_count, max_frp_mw,
                   mean_confidence, representative_candidate_id, candidate_ids,
                   status, imagery_status, is_simulated, is_replay
            FROM fire_hotspot_clusters
            WHERE {where}
            ORDER BY observed_at, cluster_id
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    )
    items = []
    for row in result.mappings().all():
        item = dict(row)
        item["observed_at"] = item["observed_at"].isoformat().replace("+00:00", "Z")
        item["location"] = {
            "longitude": item.pop("longitude"),
            "latitude": item.pop("latitude"),
            "crs": "EPSG:4326",
        }
        item["candidate_ids"] = _json_value(item.get("candidate_ids"), [])
        items.append(item)
    return {
        "schema_version": "fire.realtime.replay.v0.1",
        "event_id": event_id,
        "source": "FIRMS historical observations aggregated into ten-minute replay units",
        "interval_minutes": 10,
        "spatial_cell_degrees": 0.02,
        "is_replay": True,
        "start_at": start_at.isoformat().replace("+00:00", "Z"),
        "end_at": end_at.isoformat().replace("+00:00", "Z"),
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }
