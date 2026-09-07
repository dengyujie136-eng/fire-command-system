import math
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.observation import TrustedFirePoint
from app.models.scenario import EnvironmentSnapshot
from app.models.spread import FireFrontStep, SimulationRun
from app.schemas.spread import SpreadRunRequest
from app.services.event_service import append_timeline, get_event_or_404
from app.services.websocket_manager import websocket_manager


def _round(value: float, digits: int = 4) -> float:
    return round(float(value), digits)


def _km_to_lng(km: float, latitude: float) -> float:
    return km / max(1e-6, 111.0 * math.cos(math.radians(latitude)))


def _km_to_lat(km: float) -> float:
    return km / 111.0


def _ellipse_ring(
    center_lng: float,
    center_lat: float,
    major_km: float,
    minor_km: float,
    direction_deg: float,
    points: int = 72,
) -> list[list[float]]:
    theta = math.radians(direction_deg)
    ring: list[list[float]] = []
    for i in range(points):
        angle = 2 * math.pi * i / points
        x = major_km * math.cos(angle)
        y = minor_km * math.sin(angle)
        xr = x * math.sin(theta) + y * math.cos(theta)
        yr = x * math.cos(theta) - y * math.sin(theta)
        ring.append([_round(center_lng + _km_to_lng(xr, center_lat), 7), _round(center_lat + _km_to_lat(yr), 7)])
    ring.append(ring[0])
    return ring


def _feature(step: FireFrontStep) -> dict[str, Any]:
    return step.fireline_geojson


def build_feature_collection(steps: list[FireFrontStep]) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": [_feature(step) for step in sorted(steps, key=lambda item: item.time_minute)],
    }


async def _latest_trusted_point(db: AsyncSession, event_id: str) -> TrustedFirePoint | None:
    result = await db.execute(
        select(TrustedFirePoint)
        .where(TrustedFirePoint.event_id == event_id)
        .order_by(desc(TrustedFirePoint.created_at), desc(TrustedFirePoint.id))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _latest_environment(db: AsyncSession, event_id: str) -> EnvironmentSnapshot | None:
    result = await db.execute(
        select(EnvironmentSnapshot)
        .where(EnvironmentSnapshot.event_id == event_id)
        .order_by(desc(EnvironmentSnapshot.time_minute), desc(EnvironmentSnapshot.id))
        .limit(1)
    )
    return result.scalar_one_or_none()


def _fallback_environment() -> dict[str, Any]:
    return {
        "time_minute": 0,
        "temperature_c": 30.0,
        "humidity_percent": 32.0,
        "wind_speed_m_s": 4.0,
        "wind_direction_deg": 45.0,
        "fuel_moisture": 0.16,
        "fire_weather_index": 16.0,
    }


def _environment_payload(env: EnvironmentSnapshot | None) -> dict[str, Any]:
    if not env:
        return _fallback_environment()
    return {
        "time_minute": env.time_minute,
        "temperature_c": env.temperature_c,
        "humidity_percent": env.humidity_percent,
        "wind_speed_m_s": env.wind_speed_m_s,
        "wind_direction_deg": env.wind_direction_deg,
        "fuel_moisture": env.fuel_moisture,
        "fire_weather_index": env.fire_weather_index,
    }


async def _try_forefire(input_payload: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    url = settings.forefire_api_url.rstrip("/")
    ignition = input_payload["ignition_point"]
    duration_hours = max(0.1, float(input_payload["horizon_minutes"]) / 60.0)
    forefire_payload = {
        "model": "standard",
        "duration": duration_hours,
        "scene_id": input_payload["scenario_id"],
        "longitude": ignition["longitude"],
        "latitude": ignition["latitude"],
    }
    async with httpx.AsyncClient(timeout=settings.forefire_timeout_seconds) as client:
        response = await client.post(f"{url}/api/simulate", json=forefire_payload)
        response.raise_for_status()
        data = response.json()
    if not data.get("geojson", data if data.get("type") == "FeatureCollection" else None):
        raise RuntimeError("ForeFire response did not include fireline geojson.")
    data["_request_payload"] = forefire_payload
    return data


def _risk_level(area_km2: float, fwi: float) -> str:
    if area_km2 >= 4.5 or fwi >= 24:
        return "high"
    if area_km2 >= 1.2 or fwi >= 14:
        return "medium"
    return "low"


def _generate_fallback_steps(
    *,
    run_id: str,
    event_id: str,
    ignition_lng: float,
    ignition_lat: float,
    start_minute: int,
    horizon_minutes: int,
    step_minutes: int,
    environment: dict[str, Any],
) -> list[FireFrontStep]:
    wind_speed = float(environment.get("wind_speed_m_s") or 4.0)
    wind_direction = float(environment.get("wind_direction_deg") or 45.0)
    humidity = float(environment.get("humidity_percent") or 32.0)
    fuel_moisture = float(environment.get("fuel_moisture") or 0.16)
    fwi = float(environment.get("fire_weather_index") or 16.0)
    dryness_factor = max(0.55, min(1.85, (45 - humidity) / 28 + (0.22 - fuel_moisture) * 4.0 + fwi / 34.0))
    base_rate_m_min = max(1.2, wind_speed * 1.35 + dryness_factor * 2.1)
    steps: list[FireFrontStep] = []
    for elapsed in range(0, horizon_minutes + 1, step_minutes):
        growth_minutes = max(1, elapsed)
        downwind_km = (base_rate_m_min * growth_minutes / 1000.0) * (1.0 + min(0.65, wind_speed / 12.0))
        crosswind_km = max(0.08, downwind_km * (0.42 + max(0, 0.22 - fuel_moisture)))
        backing_km = max(0.04, downwind_km * 0.28)
        major_km = max(0.08, (downwind_km + backing_km) / 2)
        minor_km = max(0.05, crosswind_km)
        center_shift_km = max(0, (downwind_km - backing_km) / 2)
        theta = math.radians(wind_direction)
        center_lng = ignition_lng + _km_to_lng(center_shift_km * math.sin(theta), ignition_lat)
        center_lat = ignition_lat + _km_to_lat(center_shift_km * math.cos(theta))
        ring = _ellipse_ring(center_lng, center_lat, major_km, minor_km, wind_direction)
        area_km2 = math.pi * major_km * minor_km
        feature = {
            "type": "Feature",
            "properties": {
                "run_id": run_id,
                "time_minute": start_minute + elapsed,
                "elapsed_minutes": elapsed,
                "elapsed_seconds": elapsed * 60,
                "area_km2": _round(area_km2, 4),
                "radius_km": _round(max(major_km, minor_km), 4),
                "spread_direction_deg": _round(wind_direction, 1),
                "engine": "simplified_fallback",
            },
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        }
        steps.append(
            FireFrontStep(
                step_id=f"ffs_{uuid4().hex}",
                run_id=run_id,
                event_id=event_id,
                time_minute=start_minute + elapsed,
                elapsed_seconds=elapsed * 60,
                area_km2=_round(area_km2, 4),
                radius_km=_round(max(major_km, minor_km), 4),
                spread_direction_deg=_round(wind_direction, 1),
                fireline_geojson=feature,
            )
        )
    return steps


def _steps_from_forefire(
    *,
    run_id: str,
    event_id: str,
    start_minute: int,
    geojson: dict[str, Any],
) -> list[FireFrontStep]:
    steps: list[FireFrontStep] = []
    for index, feature in enumerate(geojson.get("features", [])):
        props = feature.setdefault("properties", {})
        elapsed_seconds = int(props.get("elapsed_seconds") or props.get("elapsed_minutes", index * 30) * 60 or index * 1800)
        elapsed_minutes = int(round(elapsed_seconds / 60))
        props["run_id"] = run_id
        props["time_minute"] = start_minute + elapsed_minutes
        props["elapsed_seconds"] = elapsed_seconds
        props["engine"] = props.get("engine") or "forefire"
        area = float(props.get("area_km2") or 0)
        radius = float(props.get("radius_km") or 0)
        direction = float(props.get("spread_direction_deg") or 0)
        steps.append(
            FireFrontStep(
                step_id=f"ffs_{uuid4().hex}",
                run_id=run_id,
                event_id=event_id,
                time_minute=start_minute + elapsed_minutes,
                elapsed_seconds=elapsed_seconds,
                area_km2=area,
                radius_km=radius,
                spread_direction_deg=direction,
                fireline_geojson=feature,
            )
        )
    return steps


async def create_spread_run(db: AsyncSession, event_id: str, request: SpreadRunRequest) -> dict[str, Any]:
    event = await get_event_or_404(db, event_id)
    trusted = await _latest_trusted_point(db, event_id)
    if not trusted:
        raise AppError("Trusted fire point is required before spread prediction.", code="trusted_point_required", status_code=400)
    env = await _latest_environment(db, event_id)
    env_payload = _environment_payload(env)
    run_id = f"spr_{uuid4().hex[:18]}"
    input_payload = {
        "event_id": event_id,
        "scenario_id": event.scenario_id,
        "ignition_point": {"longitude": trusted.longitude, "latitude": trusted.latitude, "confidence": trusted.confidence},
        "environment": env_payload,
        "horizon_minutes": request.horizon_minutes,
        "step_minutes": request.step_minutes,
    }
    forefire_attempted = bool(request.prefer_forefire)
    forefire_available = False
    fallback_used = True
    engine = "simplified_fallback"
    error_message = ""
    steps: list[FireFrontStep]
    if request.prefer_forefire:
        try:
            forefire_result = await _try_forefire(input_payload)
            geojson = forefire_result.get("geojson") or forefire_result
            steps = _steps_from_forefire(run_id=run_id, event_id=event_id, start_minute=env_payload["time_minute"], geojson=geojson)
            if not steps:
                raise RuntimeError("ForeFire produced no fire front steps.")
            forefire_available = True
            fallback_used = False
            engine = "forefire"
        except Exception as exc:
            error_message = str(exc)
            steps = _generate_fallback_steps(
                run_id=run_id,
                event_id=event_id,
                ignition_lng=trusted.longitude,
                ignition_lat=trusted.latitude,
                start_minute=env_payload["time_minute"],
                horizon_minutes=request.horizon_minutes,
                step_minutes=request.step_minutes,
                environment=env_payload,
            )
    else:
        steps = _generate_fallback_steps(
            run_id=run_id,
            event_id=event_id,
            ignition_lng=trusted.longitude,
            ignition_lat=trusted.latitude,
            start_minute=env_payload["time_minute"],
            horizon_minutes=request.horizon_minutes,
            step_minutes=request.step_minutes,
            environment=env_payload,
        )
    final = sorted(steps, key=lambda item: item.time_minute)[-1]
    run = SimulationRun(
        run_id=run_id,
        event_id=event_id,
        scenario_id=event.scenario_id,
        status="completed",
        engine=engine,
        forefire_attempted=forefire_attempted,
        forefire_available=forefire_available,
        fallback_used=fallback_used,
        start_minute=env_payload["time_minute"],
        horizon_minutes=request.horizon_minutes,
        step_minutes=request.step_minutes,
        ignition_longitude=trusted.longitude,
        ignition_latitude=trusted.latitude,
        final_area_km2=final.area_km2,
        max_radius_km=max(step.radius_km for step in steps),
        spread_direction_deg=final.spread_direction_deg,
        risk_level=_risk_level(final.area_km2, env_payload["fire_weather_index"]),
        input_snapshot=input_payload,
        result_summary={
            "step_count": len(steps),
            "final_time_minute": final.time_minute,
            "final_area_km2": final.area_km2,
            "max_radius_km": max(step.radius_km for step in steps),
            "usable_by_agent": True,
        },
        error_message=error_message,
    )
    db.add(run)
    await db.flush()
    await db.execute(delete(FireFrontStep).where(FireFrontStep.run_id == run_id))
    for step in steps:
        db.add(step)
    await append_timeline(
        db,
        event_id=event_id,
        event_type="spread.completed",
        status="simulating",
        title="Spread prediction completed",
        message="Early fire spread prediction has produced multi-step fire fronts for command decision support.",
        payload={
            "run_id": run_id,
            "engine": engine,
            "fallback_used": fallback_used,
            "step_count": len(steps),
            "final_area_km2": final.area_km2,
            "risk_level": run.risk_level,
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
        "spread.completed",
        {"run_id": run_id, "engine": engine, "fallback_used": fallback_used, "geojson": geojson, "summary": run.result_summary},
    )
    return {"run": run, "steps": sorted(steps, key=lambda item: item.time_minute), "geojson": geojson}


async def latest_spread_run(db: AsyncSession, event_id: str) -> dict[str, Any] | None:
    await get_event_or_404(db, event_id)
    result = await db.execute(
        select(SimulationRun).where(SimulationRun.event_id == event_id).order_by(desc(SimulationRun.created_at), desc(SimulationRun.id)).limit(1)
    )
    run = result.scalar_one_or_none()
    if not run:
        return None
    steps = await spread_steps(db, run.run_id)
    return {"run": run, "steps": steps, "geojson": build_feature_collection(steps)}


async def spread_steps(db: AsyncSession, run_id: str) -> list[FireFrontStep]:
    result = await db.execute(select(FireFrontStep).where(FireFrontStep.run_id == run_id).order_by(FireFrontStep.time_minute, FireFrontStep.id))
    return list(result.scalars().all())
