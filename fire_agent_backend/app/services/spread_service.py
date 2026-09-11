from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.observation import TrustedFirePoint
from app.models.scenario import EnvironmentSnapshot, ScenarioDefinition
from app.models.spread import FireFrontStep, SimulationRun
from app.schemas.spread import SpreadRunRequest
from app.services.event_service import append_timeline, get_event_or_404
from app.services.landscape_service import load_scenario_landscape
from app.services.scenario_registry import get_scenario_or_404
from app.services.websocket_manager import websocket_manager
from app.tools.dynamic_fire_spread import TOOL_NAME, TOOL_VERSION, run_dynamic_fire_spread


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _circular_delta(start_deg: float, end_deg: float) -> float:
    return (end_deg - start_deg + 180.0) % 360.0 - 180.0


def build_feature_collection(steps: list[FireFrontStep]) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": [
            step.fireline_geojson
            for step in sorted(steps, key=lambda item: item.time_minute)
        ],
    }


async def _latest_trusted_point(db: AsyncSession, event_id: str) -> TrustedFirePoint | None:
    result = await db.execute(
        select(TrustedFirePoint)
        .where(TrustedFirePoint.event_id == event_id)
        .order_by(desc(TrustedFirePoint.created_at), desc(TrustedFirePoint.id))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _environment_history(db: AsyncSession, event_id: str) -> list[EnvironmentSnapshot]:
    result = await db.execute(
        select(EnvironmentSnapshot)
        .where(EnvironmentSnapshot.event_id == event_id)
        .order_by(EnvironmentSnapshot.time_minute, EnvironmentSnapshot.id)
    )
    return list(result.scalars().all())


async def _spread_run_or_404(
    db: AsyncSession,
    event_id: str,
    run_id: str,
) -> SimulationRun:
    result = await db.execute(
        select(SimulationRun)
        .where(
            SimulationRun.event_id == event_id,
            SimulationRun.run_id == run_id,
        )
        .limit(1)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise AppError(
            f"Spread run not found for continuation: {run_id}",
            code="spread_parent_not_found",
            status_code=404,
        )
    return run


async def _final_step_for_run(
    db: AsyncSession,
    event_id: str,
    run_id: str,
) -> FireFrontStep:
    result = await db.execute(
        select(FireFrontStep)
        .where(
            FireFrontStep.event_id == event_id,
            FireFrontStep.run_id == run_id,
        )
        .order_by(
            desc(FireFrontStep.time_minute),
            desc(FireFrontStep.id),
        )
        .limit(1)
    )
    step = result.scalar_one_or_none()
    if not step:
        raise AppError(
            f"Spread run has no fireline checkpoint: {run_id}",
            code="spread_parent_checkpoint_missing",
            status_code=400,
        )
    return step


def _default_environment() -> dict[str, Any]:
    return {
        "temperature_c": 30.0,
        "humidity_percent": 32.0,
        "wind_speed_m_s": 4.0,
        "wind_direction_deg": 45.0,
        "fuel_moisture": 0.16,
        "fire_weather_index": 16.0,
        "precipitation_mm_h": 0.0,
    }


def _snapshot_values(snapshot: EnvironmentSnapshot) -> dict[str, Any]:
    payload = snapshot.payload or {}
    return {
        "temperature_c": snapshot.temperature_c,
        "humidity_percent": snapshot.humidity_percent,
        "wind_speed_m_s": snapshot.wind_speed_m_s,
        "wind_direction_deg": snapshot.wind_direction_deg,
        "fuel_moisture": snapshot.fuel_moisture,
        "fire_weather_index": snapshot.fire_weather_index,
        "precipitation_mm_h": float(payload.get("precipitation_mm_h") or 0),
    }


def _projection_trends(
    history: list[EnvironmentSnapshot],
) -> tuple[dict[str, float], str]:
    if len(history) < 2:
        return (
            {
                "temperature_c": 0.008,
                "humidity_percent": -0.025,
                "wind_speed_m_s": 0.006,
                "wind_direction_deg": 0.12,
                "fuel_moisture": -0.00008,
                "fire_weather_index": 0.025,
                "precipitation_mm_h": 0.0,
            },
            "database_snapshot_projection",
        )

    previous, latest = history[-2], history[-1]
    elapsed = max(1, latest.time_minute - previous.time_minute)
    before = _snapshot_values(previous)
    after = _snapshot_values(latest)
    return (
        {
            "temperature_c": _clamp(
                (after["temperature_c"] - before["temperature_c"]) / elapsed,
                -0.03,
                0.03,
            ),
            "humidity_percent": _clamp(
                (after["humidity_percent"] - before["humidity_percent"]) / elapsed,
                -0.08,
                0.08,
            ),
            "wind_speed_m_s": _clamp(
                (after["wind_speed_m_s"] - before["wind_speed_m_s"]) / elapsed,
                -0.02,
                0.02,
            ),
            "wind_direction_deg": _clamp(
                _circular_delta(
                    before["wind_direction_deg"],
                    after["wind_direction_deg"],
                )
                / elapsed,
                -0.4,
                0.4,
            ),
            "fuel_moisture": _clamp(
                (after["fuel_moisture"] - before["fuel_moisture"]) / elapsed,
                -0.0002,
                0.0002,
            ),
            "fire_weather_index": _clamp(
                (after["fire_weather_index"] - before["fire_weather_index"]) / elapsed,
                -0.06,
                0.06,
            ),
            "precipitation_mm_h": _clamp(
                (
                    after["precipitation_mm_h"]
                    - before["precipitation_mm_h"]
                )
                / elapsed,
                -0.05,
                0.05,
            ),
        },
        "database_trend_projection",
    )


def _project_environment_timeline(
    history: list[EnvironmentSnapshot],
    horizon_minutes: int,
) -> tuple[list[dict[str, Any]], str, int]:
    if history:
        latest = history[-1]
        base = _snapshot_values(latest)
        start_minute = latest.time_minute
        trends, source = _projection_trends(history)
    else:
        base = _default_environment()
        start_minute = 0
        trends = {
            "temperature_c": 0.008,
            "humidity_percent": -0.025,
            "wind_speed_m_s": 0.006,
            "wind_direction_deg": 0.12,
            "fuel_moisture": -0.00008,
            "fire_weather_index": 0.025,
            "precipitation_mm_h": 0.0,
        }
        source = "default_dynamic_projection"

    frame_minutes = [0, horizon_minutes]
    frames: list[dict[str, Any]] = []
    for elapsed in frame_minutes:
        frames.append(
            {
                "elapsed_minutes": elapsed,
                "temperature_c": _clamp(
                    base["temperature_c"]
                    + trends["temperature_c"] * elapsed,
                    -30,
                    65,
                ),
                "humidity_percent": _clamp(
                    base["humidity_percent"]
                    + trends["humidity_percent"] * elapsed,
                    0,
                    100,
                ),
                "wind_speed_m_s": _clamp(
                    base["wind_speed_m_s"]
                    + trends["wind_speed_m_s"] * elapsed,
                    0,
                    60,
                ),
                "wind_direction_deg": (
                    base["wind_direction_deg"]
                    + trends["wind_direction_deg"] * elapsed
                )
                % 360,
                "fuel_moisture": _clamp(
                    base["fuel_moisture"]
                    + trends["fuel_moisture"] * elapsed,
                    0.01,
                    0.8,
                ),
                "fire_weather_index": _clamp(
                    base["fire_weather_index"]
                    + trends["fire_weather_index"] * elapsed,
                    0,
                    100,
                ),
                "precipitation_mm_h": _clamp(
                    base["precipitation_mm_h"]
                    + trends["precipitation_mm_h"] * elapsed,
                    0,
                    200,
                ),
                "source": source,
            }
        )
    return frames, source, start_minute


def _minutes_to_next_weather_update(
    scenario: ScenarioDefinition,
    start_minute: int,
) -> int:
    for segment in scenario.time_segments or []:
        segment_start = int(segment.get("from_minute", 0))
        segment_end = int(
            segment.get("to_minute", scenario.duration_minutes)
        )
        cadence = max(1, int(segment.get("step_minutes", 5)))
        if segment_start <= start_minute < segment_end:
            offset = max(0, start_minute - segment_start)
            next_valid_minute = (
                segment_start + (offset // cadence + 1) * cadence
            )
            return max(
                1,
                min(segment_end, next_valid_minute) - start_minute,
            )
    return max(1, int((scenario.time_segments or [{}])[-1].get("step_minutes", 5)))


def _environment_input(
    request: SpreadRunRequest,
    history: list[EnvironmentSnapshot],
    scenario: ScenarioDefinition,
    start_minute: int,
) -> tuple[list[dict[str, Any]], str, int | None]:
    if request.environment_timeline:
        return (
            [item.model_dump() for item in request.environment_timeline],
            "agent_supplied_timeline",
            request.horizon_minutes,
        )
    weather_update_horizon = _minutes_to_next_weather_update(
        scenario,
        start_minute,
    )
    timeline, source, _ = _project_environment_timeline(
        history,
        weather_update_horizon,
    )
    return timeline, source, weather_update_horizon


def _steps_from_tool(
    *,
    run_id: str,
    event_id: str,
    start_minute: int,
    tool_result: dict[str, Any],
    parent_run_id: str | None,
    run_mode: str,
    initial_fireline_source: str,
) -> list[FireFrontStep]:
    steps: list[FireFrontStep] = []
    for item in tool_result.get("steps", []):
        elapsed_minutes = int(item["elapsed_minutes"])
        feature = item["fireline_geojson"]
        properties = feature.setdefault("properties", {})
        properties["run_id"] = run_id
        properties["event_id"] = event_id
        properties["time_minute"] = start_minute + elapsed_minutes
        properties["parent_run_id"] = parent_run_id
        properties["run_mode"] = run_mode
        properties["initial_fireline_source"] = initial_fireline_source
        steps.append(
            FireFrontStep(
                step_id=f"ffs_{uuid4().hex}",
                run_id=run_id,
                event_id=event_id,
                time_minute=start_minute + elapsed_minutes,
                elapsed_seconds=int(item["elapsed_seconds"]),
                area_km2=float(item["area_km2"]),
                radius_km=float(item["radius_km"]),
                spread_direction_deg=float(item["spread_direction_deg"]),
                fireline_geojson=feature,
            )
        )
    return steps


def _risk_level(area_km2: float, max_fwi: float) -> str:
    if area_km2 >= 4.5 or max_fwi >= 24:
        return "high"
    if area_km2 >= 1.2 or max_fwi >= 14:
        return "medium"
    return "low"


async def create_spread_run(
    db: AsyncSession,
    event_id: str,
    request: SpreadRunRequest,
) -> dict[str, Any]:
    event = await get_event_or_404(db, event_id)
    scenario = await get_scenario_or_404(db, event.scenario_id)
    parent_run: SimulationRun | None = None
    parent_step: FireFrontStep | None = None
    if request.continue_from_run_id:
        parent_run = await _spread_run_or_404(
            db,
            event_id,
            request.continue_from_run_id,
        )
        parent_step = await _final_step_for_run(
            db,
            event_id,
            parent_run.run_id,
        )

    trusted = await _latest_trusted_point(db, event_id)
    request_ignition = request.ignition_point
    if not trusted and not request_ignition and not parent_run:
        raise AppError(
            "Trusted fire point is required before spread prediction.",
            code="trusted_point_required",
            status_code=400,
        )

    ignition_longitude = (
        request_ignition.longitude
        if request_ignition
        else parent_run.ignition_longitude
        if parent_run
        else trusted.longitude
    )
    ignition_latitude = (
        request_ignition.latitude
        if request_ignition
        else parent_run.ignition_latitude
        if parent_run
        else trusted.latitude
    )
    ignition_confidence = (
        request_ignition.confidence
        if request_ignition
        else float(
            ((parent_run.input_snapshot or {}).get("ignition_point") or {}).get(
                "confidence",
                0.95,
            )
        )
        if parent_run
        else trusted.confidence
    )
    history = await _environment_history(db, event_id)
    start_minute = history[-1].time_minute if history else 0
    if parent_step:
        start_minute = parent_step.time_minute
    environment_timeline, environment_source, requested_horizon = _environment_input(
        request,
        history,
        scenario,
        start_minute,
    )

    initial_fireline = (
        request.initial_fireline_geojson
        or (parent_step.fireline_geojson if parent_step else None)
    )
    if request.initial_fireline_geojson:
        initial_fireline_source = (
            request.initial_fireline_source
            if request.initial_fireline_source != "ignition"
            else "agent_supplied_fireline"
        )
    elif parent_step:
        initial_fireline_source = "parent_run_final_fireline"
    else:
        initial_fireline_source = "ignition"

    run_mode = request.run_mode
    if parent_run and run_mode == "initial_forecast":
        run_mode = "rolling_forecast"

    terrain = request.terrain.model_dump(exclude_none=True)
    if request.landscape:
        landscape = request.landscape.model_dump()
        landscape_warning = None
        landscape_source = "agent_supplied_landscape"
    else:
        landscape, landscape_warning = load_scenario_landscape(event.scenario_id)
        landscape_source = (
            str(landscape.get("source") or "scenario_netcdf")
            if landscape
            else "uniform_terrain_fallback"
        )
    run_id = f"spr_{uuid4().hex[:18]}"
    parent_lineage = (
        ((parent_run.input_snapshot or {}).get("lineage") or {})
        if parent_run
        else {}
    )
    root_run_id = (
        parent_lineage.get("root_run_id")
        or (parent_run.run_id if parent_run else run_id)
    )

    try:
        tool_result = run_dynamic_fire_spread(
            ignition_longitude=ignition_longitude,
            ignition_latitude=ignition_latitude,
            environment_timeline=environment_timeline,
            horizon_minutes=requested_horizon,
            step_minutes=request.step_minutes,
            terrain=terrain,
            landscape=landscape,
            initial_radius_m=request.initial_radius_m,
            initial_fireline_geojson=initial_fireline,
        )
    except (TypeError, ValueError) as exc:
        raise AppError(
            f"Dynamic fire spread tool rejected its input: {exc}",
            code="dynamic_spread_tool_invalid_input",
            status_code=400,
        ) from exc

    steps = _steps_from_tool(
        run_id=run_id,
        event_id=event_id,
        start_minute=start_minute,
        tool_result=tool_result,
        parent_run_id=parent_run.run_id if parent_run else None,
        run_mode=run_mode,
        initial_fireline_source=initial_fireline_source,
    )
    if not steps:
        raise AppError(
            "Dynamic fire spread tool produced no fire fronts.",
            code="dynamic_spread_tool_empty",
            status_code=500,
        )

    final = steps[-1]
    max_radius = max(step.radius_km for step in steps)
    normalized_environment_timeline = tool_result["input"][
        "environment_timeline"
    ]
    normalized_terrain = tool_result["input"]["terrain"]
    normalized_landscape = tool_result["input"]["landscape"]
    effective_horizon = int(tool_result["input"]["horizon_minutes"])
    effective_step = int(tool_result["input"]["step_minutes"])
    max_fwi = max(
        float(frame["fire_weather_index"])
        for frame in normalized_environment_timeline
    )
    input_payload = {
        "event_id": event_id,
        "scenario_id": event.scenario_id,
        "ignition_point": {
            "longitude": ignition_longitude,
            "latitude": ignition_latitude,
            "confidence": ignition_confidence,
            "input_source": request.input_source,
        },
        "environment_timeline": normalized_environment_timeline,
        "environment_source": environment_source,
        "terrain": normalized_terrain,
        "landscape": normalized_landscape,
        "landscape_source": landscape_source,
        "landscape_warning": landscape_warning,
        "horizon_minutes": effective_horizon,
        "step_minutes": effective_step,
        "timing_mode": tool_result["input"]["timing_mode"],
        "weather_update_minutes": tool_result["input"][
            "weather_update_minutes"
        ],
        "initial_radius_m": request.initial_radius_m,
        "initial_fireline_geojson": initial_fireline,
        "initial_fireline_source": initial_fireline_source,
        "lineage": {
            "parent_run_id": parent_run.run_id if parent_run else None,
            "root_run_id": root_run_id,
            "run_mode": run_mode,
            "generation": int(parent_lineage.get("generation") or 0)
            + (1 if parent_run else 0),
        },
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
    }
    run = SimulationRun(
        run_id=run_id,
        event_id=event_id,
        scenario_id=event.scenario_id,
        status="completed",
        engine="dynamic_agent_tool",
        forefire_attempted=False,
        forefire_available=False,
        fallback_used=False,
        start_minute=start_minute,
        horizon_minutes=effective_horizon,
        step_minutes=effective_step,
        ignition_longitude=ignition_longitude,
        ignition_latitude=ignition_latitude,
        final_area_km2=final.area_km2,
        max_radius_km=max_radius,
        spread_direction_deg=final.spread_direction_deg,
        risk_level=_risk_level(final.area_km2, max_fwi),
        input_snapshot=input_payload,
        result_summary={
            **tool_result["summary"],
            "final_time_minute": final.time_minute,
            "usable_by_agent": True,
            "dynamic_environment": True,
            "environment_source": environment_source,
            "timing_mode": tool_result["summary"]["timing_mode"],
            "weather_update_minutes": tool_result["summary"][
                "weather_update_minutes"
            ],
            "forecast_valid_until_minute": (
                start_minute
                + int(tool_result["summary"]["forecast_valid_until_minute"])
            ),
            "landscape_source": landscape_source,
            "landscape_warning": landscape_warning,
            "terrain_aware": bool(normalized_landscape.get("terrain_aware")),
            "landcover_aware": bool(normalized_landscape.get("landcover_aware")),
            "input_source": request.input_source,
            "uses_temporary_ignition": bool(request_ignition),
            "legacy_prefer_forefire_ignored": bool(request.prefer_forefire),
            "parent_run_id": parent_run.run_id if parent_run else None,
            "root_run_id": root_run_id,
            "run_mode": run_mode,
            "initial_fireline_source": initial_fireline_source,
            "continued_from_checkpoint_minute": (
                parent_step.time_minute if parent_step else None
            ),
        },
        error_message="",
    )
    db.add(run)
    await db.flush()
    for step in steps:
        db.add(step)
    await append_timeline(
        db,
        event_id=event_id,
        event_type=(
            "spread.continued"
            if parent_run
            else "spread.completed"
        ),
        status="simulating",
        title=(
            "Rolling spread forecast completed"
            if parent_run
            else "Dynamic spread tool completed"
        ),
        message=(
            "The previous final fireline checkpoint was continued with updated "
            "environment frames."
            if parent_run
            else "Time-varying environment frames produced a new multi-step "
            "fireline forecast."
        ),
        payload={
            "run_id": run_id,
            "engine": run.engine,
            "dynamic_environment": True,
            "environment_source": environment_source,
            "environment_frame_count": tool_result["summary"][
                "environment_frame_count"
            ],
            "landscape_source": landscape_source,
            "terrain_aware": bool(normalized_landscape.get("terrain_aware")),
            "landcover_aware": bool(normalized_landscape.get("landcover_aware")),
            "parent_run_id": parent_run.run_id if parent_run else None,
            "root_run_id": root_run_id,
            "run_mode": run_mode,
            "start_minute": start_minute,
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
        {
            "run_id": run_id,
            "engine": run.engine,
            "dynamic_environment": True,
            "parent_run_id": parent_run.run_id if parent_run else None,
            "run_mode": run_mode,
            "geojson": geojson,
            "summary": run.result_summary,
        },
    )
    return {"run": run, "steps": steps, "geojson": geojson}


async def latest_spread_run(
    db: AsyncSession,
    event_id: str,
) -> dict[str, Any] | None:
    await get_event_or_404(db, event_id)
    result = await db.execute(
        select(SimulationRun)
        .where(SimulationRun.event_id == event_id)
        .order_by(desc(SimulationRun.created_at), desc(SimulationRun.id))
        .limit(1)
    )
    run = result.scalar_one_or_none()
    if not run:
        return None
    steps = await spread_steps(db, run.run_id)
    return {
        "run": run,
        "steps": steps,
        "geojson": build_feature_collection(steps),
    }


async def spread_steps(
    db: AsyncSession,
    run_id: str,
) -> list[FireFrontStep]:
    result = await db.execute(
        select(FireFrontStep)
        .where(FireFrontStep.run_id == run_id)
        .order_by(FireFrontStep.time_minute, FireFrontStep.id)
    )
    return list(result.scalars().all())
