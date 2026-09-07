import asyncio
import math
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.session import AsyncSessionLocal
from app.models.event import FireEvent
from app.models.observation import EvidenceChain, FusionResult, Observation, TrustedFirePoint
from app.models.scenario import EnvironmentSnapshot, ScenarioDefinition, SimulationClock
from app.schemas.clock import ClockStartRequest, ClockStepRequest
from app.services.event_service import append_timeline, get_event_or_404
from app.services.scenario_registry import get_scenario_or_404
from app.services.websocket_manager import websocket_manager


_clock_tasks: dict[str, asyncio.Task] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _round(value: float, digits: int = 4) -> float:
    return round(float(value), digits)


def _next_step(clock: SimulationClock) -> int:
    for segment in clock.time_segments or []:
        start = int(segment.get("from_minute", 0))
        end = int(segment.get("to_minute", clock.duration_minutes))
        if start <= clock.current_minute < end:
            return int(segment.get("step_minutes", 5))
    return 5


def _event_time(event: FireEvent, minute: int) -> datetime:
    started_at = event.started_at or _now()
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    return started_at + timedelta(minutes=minute)


def _scenario_phase(scenario: ScenarioDefinition, minute: int) -> float:
    return _clamp(minute / max(1, scenario.duration_minutes), 0, 1)


def _environment_values(scenario: ScenarioDefinition, minute: int) -> dict[str, Any]:
    phase = _scenario_phase(scenario, minute)
    profile = scenario.profiles or {}
    is_pingyao = scenario.scenario_id.startswith("pingyao")
    base_temp = 27.0 if not is_pingyao else 31.0
    base_humidity = 35.0 if not is_pingyao else 29.0
    base_wind = 3.6 if not is_pingyao else 4.8
    wind_shift = 28.0 if not is_pingyao else 46.0
    diurnal = math.sin(phase * math.pi)
    gust = math.sin((minute + 7) / 17.0)
    temperature = base_temp + diurnal * (5.2 if not is_pingyao else 6.6) + 0.35 * gust
    humidity = base_humidity - diurnal * (8.0 if not is_pingyao else 10.0) - 1.5 * gust
    wind_speed = base_wind + phase * (1.5 if not is_pingyao else 2.3) + abs(gust) * 0.9
    wind_direction = (315.0 if not is_pingyao else 45.0) + wind_shift * phase + 8.0 * gust
    fuel_moisture = _clamp(0.18 - phase * (0.045 if not is_pingyao else 0.06) - diurnal * 0.02, 0.06, 0.28)
    fire_weather_index = _clamp((temperature - 18) * 0.42 + wind_speed * 1.15 + (45 - humidity) * 0.16 + (0.2 - fuel_moisture) * 16, 1, 38)
    return {
        "temperature_c": _round(temperature, 1),
        "humidity_percent": _round(_clamp(humidity, 8, 95), 1),
        "wind_speed_m_s": _round(wind_speed, 1),
        "wind_direction_deg": _round(wind_direction % 360, 1),
        "fuel_moisture": _round(fuel_moisture, 3),
        "fire_weather_index": _round(fire_weather_index, 1),
        "payload": {
            "profile": profile,
            "phase": _round(phase, 3),
            "wind_label": "northwest" if not is_pingyao else "northeast",
            "generation": "time_indexed_environment",
        },
    }


def _source_schedule(scenario: ScenarioDefinition, minute: int) -> list[dict[str, Any]]:
    phase = _scenario_phase(scenario, minute)
    lng = scenario.longitude
    lat = scenario.latitude
    schedule = [
        {
            "minute": 0,
            "source_type": "satellite",
            "source_name": "fy4_thermal",
            "stage": "wide_scan",
            "offset": (-0.0023, 0.0032),
            "confidence": 0.61,
            "attributes": {"thermal_anomaly": True, "pixel_size_m": 1000, "chain_stage": "wide_scan"},
        },
        {
            "minute": 5,
            "source_type": "ground_sensor",
            "source_name": "ground_sensor_12",
            "stage": "ground_environment_anomaly",
            "offset": (0.0008, -0.0007),
            "confidence": 0.72,
            "attributes": {"smoke_ug_m3": 132, "chain_stage": "four_layer_ground"},
        },
        {
            "minute": 10,
            "source_type": "canopy_sensor",
            "source_name": "canopy_robot_03",
            "stage": "canopy_anomaly",
            "offset": (-0.0009, -0.0011),
            "confidence": 0.76,
            "attributes": {"canopy_stress_index": 0.68, "chain_stage": "four_layer_canopy"},
        },
        {
            "minute": 15,
            "source_type": "watchtower",
            "source_name": "watchtower_northwest",
            "stage": "high_point_smoke_detection",
            "offset": (-0.0016, -0.0018),
            "confidence": 0.81,
            "attributes": {"smoke_detected": True, "visibility_km": 7.2, "chain_stage": "four_layer_high_point"},
        },
        {
            "minute": 20,
            "source_type": "satellite",
            "source_name": "gaofen_infrared",
            "stage": "precision_filter",
            "offset": (-0.0005, 0.0009),
            "confidence": 0.84,
            "attributes": {"cloud_filtered": True, "industrial_heat_filtered": True, "pixel_size_m": 30},
        },
        {
            "minute": 25,
            "source_type": "uav",
            "source_name": "uav_01",
            "stage": "low_altitude_review",
            "offset": (0.0002, -0.0002),
            "confidence": 0.91,
            "attributes": {"thermal_confirmed": True, "smoke_visible": True, "altitude_m": 260},
        },
    ]
    extra: list[dict[str, Any]] = []
    if minute > 25 and minute % 15 == 0:
        drift_lng = 0.00035 * min(10, minute // 15)
        drift_lat = 0.00022 * min(10, minute // 15)
        extra.append(
            {
                "minute": minute,
                "source_type": "uav",
                "source_name": f"uav_track_{minute}",
                "stage": "spread_tracking",
                "offset": (drift_lng, drift_lat),
                "confidence": _clamp(0.82 + phase * 0.08, 0.82, 0.94),
                "attributes": {"front_expansion_hint": "downwind", "time_minute": minute},
            }
        )
    ready = [item for item in schedule if item["minute"] == minute]
    return [
        {
            **item,
            "longitude": _round(lng + item["offset"][0], 7),
            "latitude": _round(lat + item["offset"][1], 7),
        }
        for item in [*ready, *extra]
    ]


def _source_reliability(source_type: str) -> float:
    return {
        "satellite": 0.78,
        "uav": 0.93,
        "watchtower": 0.82,
        "canopy_sensor": 0.74,
        "ground_sensor": 0.79,
    }.get(source_type, 0.7)


def _level_from_confidence(confidence: float) -> str:
    if confidence >= 0.9:
        return "high"
    if confidence >= 0.78:
        return "medium"
    return "low"


async def _get_clock(db: AsyncSession, event_id: str) -> SimulationClock:
    result = await db.execute(select(SimulationClock).where(SimulationClock.event_id == event_id))
    clock = result.scalar_one_or_none()
    if not clock:
        event = await get_event_or_404(db, event_id)
        scenario = await get_scenario_or_404(db, event.scenario_id)
        clock = SimulationClock(
            event_id=event_id,
            scenario_id=scenario.scenario_id,
            status="idle",
            current_minute=0,
            duration_minutes=scenario.duration_minutes,
            tick_interval_seconds=scenario.default_tick_interval_seconds,
            time_segments=scenario.time_segments,
        )
        db.add(clock)
        await db.flush()
    return clock


async def _latest_environment(db: AsyncSession, event_id: str) -> EnvironmentSnapshot | None:
    result = await db.execute(
        select(EnvironmentSnapshot)
        .where(EnvironmentSnapshot.event_id == event_id)
        .order_by(desc(EnvironmentSnapshot.time_minute), desc(EnvironmentSnapshot.id))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _latest_fusion(db: AsyncSession, event_id: str) -> FusionResult | None:
    result = await db.execute(
        select(FusionResult).where(FusionResult.event_id == event_id).order_by(desc(FusionResult.created_at), desc(FusionResult.id)).limit(1)
    )
    return result.scalar_one_or_none()


async def _latest_trusted(db: AsyncSession, event_id: str) -> TrustedFirePoint | None:
    result = await db.execute(
        select(TrustedFirePoint)
        .where(TrustedFirePoint.event_id == event_id)
        .order_by(desc(TrustedFirePoint.created_at), desc(TrustedFirePoint.id))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def clock_state(db: AsyncSession, event_id: str) -> dict[str, Any]:
    clock = await _get_clock(db, event_id)
    observations = list(
        (
            await db.execute(
                select(Observation).where(Observation.event_id == event_id).order_by(Observation.observed_at, Observation.id)
            )
        )
        .scalars()
        .all()
    )
    return {
        "clock": clock,
        "environment": await _latest_environment(db, event_id),
        "observations": observations,
        "fusion_result": await _latest_fusion(db, event_id),
        "trusted_fire_point": await _latest_trusted(db, event_id),
    }


async def reset_clock(db: AsyncSession, event_id: str) -> dict[str, Any]:
    event = await get_event_or_404(db, event_id)
    scenario = await get_scenario_or_404(db, event.scenario_id)
    await stop_clock_task(event_id)
    for model in (TrustedFirePoint, FusionResult, EvidenceChain, Observation, EnvironmentSnapshot):
        await db.execute(delete(model).where(model.event_id == event_id))
    clock = await _get_clock(db, event_id)
    clock.status = "idle"
    clock.current_minute = 0
    clock.duration_minutes = scenario.duration_minutes
    clock.tick_interval_seconds = scenario.default_tick_interval_seconds
    clock.time_segments = scenario.time_segments
    clock.started_at = None
    event.status = "created"
    await append_timeline(
        db,
        event_id=event_id,
        event_type="clock.reset",
        status=event.status,
        title="Scenario clock reset",
        message="Scenario playback has been reset to the initial discovery moment.",
        payload={"current_minute": 0},
        broadcast=True,
    )
    await db.commit()
    await db.refresh(clock)
    await websocket_manager.broadcast_event(event_id, "clock.reset", {"current_minute": 0})
    return await clock_state(db, event_id)


async def pause_clock(db: AsyncSession, event_id: str) -> dict[str, Any]:
    await stop_clock_task(event_id)
    clock = await _get_clock(db, event_id)
    clock.status = "paused"
    await append_timeline(
        db,
        event_id=event_id,
        event_type="clock.paused",
        status="paused",
        title="Scenario clock paused",
        message="Scenario playback has been paused.",
        payload={"current_minute": clock.current_minute},
        broadcast=True,
    )
    await db.commit()
    await db.refresh(clock)
    await websocket_manager.broadcast_event(event_id, "clock.paused", {"current_minute": clock.current_minute})
    return await clock_state(db, event_id)


async def start_clock(db: AsyncSession, event_id: str, request: ClockStartRequest) -> dict[str, Any]:
    event = await get_event_or_404(db, event_id)
    if request.scenario_id and request.scenario_id != event.scenario_id:
        raise AppError("Clock scenario_id must match the event scenario_id.", code="scenario_mismatch", status_code=400)
    if request.reset:
        await reset_clock(db, event_id)
        event = await get_event_or_404(db, event_id)
    clock = await _get_clock(db, event_id)
    if request.tick_interval_seconds is not None:
        clock.tick_interval_seconds = request.tick_interval_seconds
    clock.status = "running"
    if clock.started_at is None:
        clock.started_at = _now()
    event.status = "observing"
    await append_timeline(
        db,
        event_id=event_id,
        event_type="clock.started",
        status=event.status,
        title="Scenario clock started",
        message="Time-ordered fire situation playback has started.",
        payload={"current_minute": clock.current_minute, "duration_minutes": clock.duration_minutes},
        broadcast=True,
    )
    await db.commit()
    await db.refresh(clock)
    await websocket_manager.broadcast_event(
        event_id,
        "clock.started",
        {"current_minute": clock.current_minute, "duration_minutes": clock.duration_minutes},
    )
    if not await _latest_environment(db, event_id):
        await step_clock(db, event_id, ClockStepRequest(minutes=1))
    _ensure_clock_task(event_id)
    return await clock_state(db, event_id)


async def resume_clock(db: AsyncSession, event_id: str) -> dict[str, Any]:
    clock = await _get_clock(db, event_id)
    if clock.current_minute >= clock.duration_minutes:
        raise AppError("Scenario clock has already reached its duration.", code="clock_finished", status_code=400)
    clock.status = "running"
    await append_timeline(
        db,
        event_id=event_id,
        event_type="clock.resumed",
        status="running",
        title="Scenario clock resumed",
        message="Scenario playback has resumed.",
        payload={"current_minute": clock.current_minute},
        broadcast=True,
    )
    await db.commit()
    await db.refresh(clock)
    await websocket_manager.broadcast_event(event_id, "clock.resumed", {"current_minute": clock.current_minute})
    _ensure_clock_task(event_id)
    return await clock_state(db, event_id)


async def step_clock(db: AsyncSession, event_id: str, request: ClockStepRequest | None = None) -> dict[str, Any]:
    event = await get_event_or_404(db, event_id)
    clock = await _get_clock(db, event_id)
    scenario = await get_scenario_or_404(db, clock.scenario_id)
    step_minutes = request.minutes if request and request.minutes else _next_step(clock)
    next_minute = min(clock.duration_minutes, clock.current_minute + step_minutes)
    if clock.current_minute == 0 and not await _latest_environment(db, event_id):
        next_minute = 0
    if next_minute == clock.current_minute and clock.current_minute != 0:
        clock.status = "completed"
        event.status = "confirmed" if await _latest_trusted(db, event_id) else event.status
        await db.commit()
        return await clock_state(db, event_id)

    clock.current_minute = next_minute
    env = await _upsert_environment(db, event, scenario, next_minute)
    new_observations = await _create_due_observations(db, event, scenario, next_minute)
    fusion = await _update_fusion(db, event, scenario)
    trusted = await _maybe_confirm_trusted_point(db, event, fusion)
    event.status = "confirmed" if trusted else "observing"
    if clock.current_minute >= clock.duration_minutes:
        clock.status = "completed"
    await append_timeline(
        db,
        event_id=event_id,
        event_type="clock.tick",
        status=event.status,
        title=f"Scenario minute {clock.current_minute}",
        message="Scenario clock advanced and generated the latest situation snapshot.",
        payload={
            "current_minute": clock.current_minute,
            "observation_count": len(new_observations),
            "fusion_confidence": fusion.confidence if fusion else None,
            "trusted_confirmed": bool(trusted),
        },
        broadcast=True,
    )
    await db.commit()
    await db.refresh(clock)
    await db.refresh(env)
    if fusion:
        await db.refresh(fusion)
    if trusted:
        await db.refresh(trusted)
    await websocket_manager.broadcast_event(
        event_id,
        "clock.tick",
        {
            "current_minute": clock.current_minute,
            "status": clock.status,
            "observation_count": len(new_observations),
            "fusion_confidence": fusion.confidence if fusion else None,
            "trusted_confirmed": bool(trusted),
        },
    )
    await websocket_manager.broadcast_event(event_id, "environment.updated", _environment_payload(env))
    for obs in new_observations:
        await websocket_manager.broadcast_event(event_id, "observation.created", _observation_payload(obs))
    if fusion:
        await websocket_manager.broadcast_event(event_id, "fusion.updated", _fusion_payload(fusion))
    if trusted:
        await websocket_manager.broadcast_event(event_id, "trusted_fire_point.confirmed", _trusted_payload(trusted))
    return await clock_state(db, event_id)


async def _upsert_environment(db: AsyncSession, event: FireEvent, scenario: ScenarioDefinition, minute: int) -> EnvironmentSnapshot:
    snapshot_id = f"env_{event.event_id}_{minute:04d}"
    result = await db.execute(select(EnvironmentSnapshot).where(EnvironmentSnapshot.snapshot_id == snapshot_id))
    existing = result.scalar_one_or_none()
    values = _environment_values(scenario, minute)
    if existing:
        for key, value in values.items():
            setattr(existing, key, value)
        return existing
    env = EnvironmentSnapshot(
        snapshot_id=snapshot_id,
        event_id=event.event_id,
        scenario_id=scenario.scenario_id,
        time_minute=minute,
        **values,
    )
    db.add(env)
    await db.flush()
    return env


async def _create_due_observations(
    db: AsyncSession,
    event: FireEvent,
    scenario: ScenarioDefinition,
    minute: int,
) -> list[Observation]:
    created: list[Observation] = []
    observed_at = _event_time(event, minute)
    env_values = _environment_values(scenario, minute)
    for item in _source_schedule(scenario, minute):
        observation_id = f"obs_{event.event_id}_{minute:04d}_{item['source_type']}_{item['source_name']}"
        result = await db.execute(select(Observation).where(Observation.observation_id == observation_id))
        if result.scalar_one_or_none():
            continue
        attrs = {
            **item["attributes"],
            "time_minute": minute,
            "temperature_c": env_values["temperature_c"],
            "humidity_percent": env_values["humidity_percent"],
            "wind_speed_m_s": env_values["wind_speed_m_s"],
            "wind_direction_deg": env_values["wind_direction_deg"],
        }
        obs = Observation(
            observation_id=observation_id,
            event_id=event.event_id,
            source_type=item["source_type"],
            source_name=item["source_name"],
            stage=item["stage"],
            longitude=item["longitude"],
            latitude=item["latitude"],
            confidence=_round(item["confidence"], 3),
            observed_at=observed_at,
            attributes=attrs,
            is_simulated=True,
            data_source_mode="simulation",
        )
        db.add(obs)
        created.append(obs)
    await db.flush()
    for obs in created:
        reliability = _source_reliability(obs.source_type)
        db.add(
            EvidenceChain(
                evidence_id=f"evd_{uuid4().hex}",
                event_id=event.event_id,
                observation_id=obs.observation_id,
                source_type=obs.source_type,
                reliability=reliability,
                weight=_round(reliability / 5.0, 4),
                contribution=_round(obs.confidence * reliability, 4),
                explanation=f"{obs.source_type} evidence contributed at minute {minute}.",
            )
        )
    await db.flush()
    return created


async def _update_fusion(db: AsyncSession, event: FireEvent, scenario: ScenarioDefinition) -> FusionResult | None:
    observations = list(
        (
            await db.execute(
                select(Observation).where(Observation.event_id == event.event_id).order_by(Observation.observed_at, Observation.id)
            )
        )
        .scalars()
        .all()
    )
    if not observations:
        return None
    sources = sorted({item.source_type for item in observations})
    weighted = sum(item.confidence * _source_reliability(item.source_type) for item in observations)
    denom = sum(_source_reliability(item.source_type) for item in observations)
    confidence = _clamp((weighted / max(denom, 0.001)) * (0.72 + 0.07 * len(sources)), 0.45, 0.96)
    lng = sum(item.longitude * item.confidence for item in observations) / sum(item.confidence for item in observations)
    lat = sum(item.latitude * item.confidence for item in observations) / sum(item.confidence for item in observations)
    confirmed = confidence >= 0.82 and len(sources) >= 3
    fusion = FusionResult(
        fusion_id=f"fus_{uuid4().hex}",
        event_id=event.event_id,
        confirmed=confirmed,
        confidence=_round(confidence, 3),
        longitude=_round(lng, 7),
        latitude=_round(lat, 7),
        evidence_count=len(observations),
        evidence_sources=sources,
        decision="trusted_fire_point" if confirmed else "continue_observation",
        quality={
            "completeness": _round(min(1, len(sources) / 5), 3),
            "accuracy": _round(confidence, 3),
            "source_count": len(sources),
            "observation_count": len(observations),
            "scenario_id": scenario.scenario_id,
        },
        is_simulated=True,
        data_source_mode="simulation",
    )
    db.add(fusion)
    await db.flush()
    return fusion


async def _maybe_confirm_trusted_point(db: AsyncSession, event: FireEvent, fusion: FusionResult | None) -> TrustedFirePoint | None:
    if not fusion or not fusion.confirmed:
        return await _latest_trusted(db, event.event_id)
    existing = await _latest_trusted(db, event.event_id)
    if existing:
        existing.fusion_id = fusion.fusion_id
        existing.longitude = fusion.longitude
        existing.latitude = fusion.latitude
        existing.confidence = fusion.confidence
        existing.level = _level_from_confidence(fusion.confidence)
        return existing
    trusted = TrustedFirePoint(
        trusted_point_id=f"tfp_{uuid4().hex}",
        event_id=event.event_id,
        fusion_id=fusion.fusion_id,
        longitude=fusion.longitude,
        latitude=fusion.latitude,
        confidence=fusion.confidence,
        level=_level_from_confidence(fusion.confidence),
        description="Trusted fire point confirmed by time-ordered multi-source evidence.",
        is_simulated=True,
        data_source_mode="simulation",
    )
    db.add(trusted)
    await db.flush()
    await append_timeline(
        db,
        event_id=event.event_id,
        event_type="trusted_fire_point.confirmed",
        status="confirmed",
        title="Trusted fire point confirmed",
        message="Multi-source evidence reached the confirmation threshold.",
        payload={"confidence": fusion.confidence, "evidence_count": fusion.evidence_count},
        broadcast=True,
    )
    return trusted


def _ensure_clock_task(event_id: str) -> None:
    task = _clock_tasks.get(event_id)
    if task and not task.done():
        return
    _clock_tasks[event_id] = asyncio.create_task(_run_clock(event_id))


async def stop_clock_task(event_id: str) -> None:
    task = _clock_tasks.pop(event_id, None)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def _run_clock(event_id: str) -> None:
    while True:
        async with AsyncSessionLocal() as db:
            clock = await _get_clock(db, event_id)
            if clock.status != "running":
                return
            interval = clock.tick_interval_seconds
            if clock.current_minute >= clock.duration_minutes:
                clock.status = "completed"
                await db.commit()
                return
        await asyncio.sleep(interval)
        async with AsyncSessionLocal() as db:
            clock = await _get_clock(db, event_id)
            if clock.status != "running":
                return
            await step_clock(db, event_id, ClockStepRequest())


def _environment_payload(env: EnvironmentSnapshot) -> dict[str, Any]:
    return {
        "snapshot_id": env.snapshot_id,
        "event_id": env.event_id,
        "scenario_id": env.scenario_id,
        "time_minute": env.time_minute,
        "temperature_c": env.temperature_c,
        "humidity_percent": env.humidity_percent,
        "wind_speed_m_s": env.wind_speed_m_s,
        "wind_direction_deg": env.wind_direction_deg,
        "fuel_moisture": env.fuel_moisture,
        "fire_weather_index": env.fire_weather_index,
        "payload": env.payload,
    }


def _observation_payload(obs: Observation) -> dict[str, Any]:
    return {
        "observation_id": obs.observation_id,
        "event_id": obs.event_id,
        "source_type": obs.source_type,
        "source_name": obs.source_name,
        "stage": obs.stage,
        "longitude": obs.longitude,
        "latitude": obs.latitude,
        "confidence": obs.confidence,
        "observed_at": obs.observed_at.isoformat() if obs.observed_at else None,
        "attributes": obs.attributes,
    }


def _fusion_payload(fusion: FusionResult) -> dict[str, Any]:
    return {
        "fusion_id": fusion.fusion_id,
        "event_id": fusion.event_id,
        "confirmed": fusion.confirmed,
        "confidence": fusion.confidence,
        "longitude": fusion.longitude,
        "latitude": fusion.latitude,
        "evidence_count": fusion.evidence_count,
        "evidence_sources": fusion.evidence_sources,
        "decision": fusion.decision,
        "quality": fusion.quality,
    }


def _trusted_payload(trusted: TrustedFirePoint) -> dict[str, Any]:
    return {
        "trusted_point_id": trusted.trusted_point_id,
        "event_id": trusted.event_id,
        "fusion_id": trusted.fusion_id,
        "longitude": trusted.longitude,
        "latitude": trusted.latitude,
        "confidence": trusted.confidence,
        "level": trusted.level,
        "description": trusted.description,
    }
