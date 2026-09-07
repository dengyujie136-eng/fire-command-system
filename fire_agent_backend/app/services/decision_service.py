from typing import Any
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.llm.providers import get_llm_provider
from app.models.decision import AgentPacket, DecisionRun
from app.models.observation import FusionResult, TrustedFirePoint
from app.models.scenario import EnvironmentSnapshot
from app.models.spread import FireFrontStep, SimulationRun
from app.schemas.decision import DecisionRunRequest
from app.services.event_service import append_timeline, get_event_or_404
from app.services.websocket_manager import websocket_manager


PACKET_TYPES = [
    "situation_packet",
    "risk_packet",
    "plan_packet",
    "recommendation_packet",
    "uav_recommendation_packet",
    "route_recommendation_packet",
    "resource_recommendation_packet",
    "report_packet",
]


def _round(value: float, digits: int = 3) -> float:
    return round(float(value), digits)


async def _latest(db: AsyncSession, model: Any, event_id: str):
    result = await db.execute(select(model).where(model.event_id == event_id).order_by(desc(model.created_at), desc(model.id)).limit(1))
    return result.scalar_one_or_none()


async def _spread_steps(db: AsyncSession, run_id: str) -> list[FireFrontStep]:
    result = await db.execute(select(FireFrontStep).where(FireFrontStep.run_id == run_id).order_by(FireFrontStep.time_minute, FireFrontStep.id))
    return list(result.scalars().all())


def _risk_level(area: float, fwi: float, confidence: float) -> str:
    if area >= 4.5 or fwi >= 24 or confidence >= 0.9:
        return "high"
    if area >= 1.2 or fwi >= 14 or confidence >= 0.78:
        return "medium"
    return "low"


def _risk_label(level: str) -> str:
    return {"high": "high", "medium": "medium", "low": "low"}.get(level, level)



def _offset_point(lng: float, lat: float, east_km: float, north_km: float) -> dict[str, float]:
    import math

    lat_delta = north_km / 111.0
    lng_delta = east_km / max(1e-6, 111.0 * math.cos(math.radians(lat)))
    return {"longitude": round(lng + lng_delta, 7), "latitude": round(lat + lat_delta, 7)}


def _dispatch_zones(trusted: TrustedFirePoint, env: EnvironmentSnapshot, max_radius_km: float, risk_level: str) -> list[dict[str, Any]]:
    import math

    lng = float(trusted.longitude)
    lat = float(trusted.latitude)
    radius = max(0.8, float(max_radius_km or 0.8))
    downwind = math.radians(float(env.wind_direction_deg or 0))
    crosswind = downwind + math.pi / 2
    upwind = downwind + math.pi

    def vector(angle: float, distance: float) -> tuple[float, float]:
        return math.sin(angle) * distance, math.cos(angle) * distance

    def polygon(center_angle: float, distance: float, length: float, width: float) -> list[dict[str, float]]:
        ce, cn = vector(center_angle, distance)
        le, ln = vector(center_angle, length / 2)
        we, wn = vector(center_angle + math.pi / 2, width / 2)
        corners = [
            (ce - le - we, cn - ln - wn),
            (ce + le - we, cn + ln - wn),
            (ce + le + we, cn + ln + wn),
            (ce - le + we, cn - ln + wn),
            (ce - le - we, cn - ln - wn),
        ]
        return [_offset_point(lng, lat, east, north) for east, north in corners]

    priority = "critical" if risk_level == "high" else "high"
    return [
        {
            "zone_id": "A",
            "name": "A区 下风向重点监测与保护区",
            "type": "downwind_priority",
            "priority": priority,
            "color": "#ef4444",
            "summary": "下风向扩展风险最高，前置保护目标力量与无人机复核任务。",
            "recommended_resource": "保护目标前置组、无人机热红外复核、通信保障",
            "coordinates": polygon(downwind, radius * 0.95, radius * 1.55, radius * 0.9),
        },
        {
            "zone_id": "B",
            "name": "B区 侧翼控制与备用通道区",
            "type": "flank_control",
            "priority": "high",
            "color": "#f59e0b",
            "summary": "侧翼用于观察火线偏转和维持备用通道可用。",
            "recommended_resource": "机动巡查组、备用通道保障、道路状态回传",
            "coordinates": polygon(crosswind, radius * 0.75, radius * 1.25, radius * 0.75),
        },
        {
            "zone_id": "C",
            "name": "C区 上风向指挥与集结安全区",
            "type": "upwind_command",
            "priority": "normal",
            "color": "#22c55e",
            "summary": "上风向作为临时指挥、集结和后勤保障位置。",
            "recommended_resource": "前方指挥组、医疗与后勤保障、通信中继",
            "coordinates": polygon(upwind, radius * 0.8, radius * 1.15, radius * 0.8),
        },
    ]

def _build_packets(
    *,
    decision_run_id: str,
    event_id: str,
    event_name: str,
    provider: str,
    model: str,
    trusted: TrustedFirePoint,
    fusion: FusionResult | None,
    env: EnvironmentSnapshot,
    spread: SimulationRun,
    steps: list[FireFrontStep],
    llm_text: str,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    final_step = steps[-1] if steps else None
    final_area = float(spread.final_area_km2 or (final_step.area_km2 if final_step else 0) or 0)
    max_radius = float(spread.max_radius_km or (final_step.radius_km if final_step else 0) or 0)
    avg_growth = final_area / max(0.5, spread.horizon_minutes / 60)
    risk_level = _risk_level(final_area, env.fire_weather_index, trusted.confidence)
    warnings: list[str] = []
    if spread.fallback_used:
        warnings.append("ForeFire is unavailable for this run; simplified spread fallback was used.")
    if env.wind_speed_m_s >= 5:
        warnings.append("Wind speed is high; monitor downwind fireline expansion closely.")
    if env.humidity_percent <= 30:
        warnings.append("Humidity is low; dry fuel risk is elevated.")

    input_summary = {
        "event_name": event_name,
        "trusted_point": {
            "longitude": trusted.longitude,
            "latitude": trusted.latitude,
            "confidence": trusted.confidence,
        },
        "fusion_confidence": fusion.confidence if fusion else trusted.confidence,
        "final_area_km2": _round(final_area, 3),
        "max_radius_km": _round(max_radius, 3),
        "avg_growth_km2_per_hour": _round(avg_growth, 3),
        "risk_level": risk_level,
        "risk_label": _risk_label(risk_level),
        "wind_speed_m_s": env.wind_speed_m_s,
        "wind_direction_deg": env.wind_direction_deg,
        "fire_weather_index": env.fire_weather_index,
        "spread_run_id": spread.run_id,
        "spread_engine": spread.engine,
    }

    situation_packet = {
        "summary": f"{event_name}: trusted fire point confirmed with confidence {input_summary['fusion_confidence']:.2f}.",
        "trusted_point": input_summary["trusted_point"],
        "environment": {
            "temperature_c": env.temperature_c,
            "humidity_percent": env.humidity_percent,
            "wind_speed_m_s": env.wind_speed_m_s,
            "wind_direction_deg": env.wind_direction_deg,
            "fire_weather_index": env.fire_weather_index,
        },
    }
    risk_packet = {
        "risk_level": risk_level,
        "risk_label": _risk_label(risk_level),
        "summary": f"Projected burned area is about {final_area:.2f} km2 within {spread.horizon_minutes} minutes; max radius is about {max_radius:.2f} km.",
        "drivers": ["wind", "fuel moisture", "fire weather index", "trusted point confidence"],
        "spread": {
            "run_id": spread.run_id,
            "engine": spread.engine,
            "fallback_used": spread.fallback_used,
            "step_count": len(steps),
            "final_area_km2": _round(final_area, 3),
            "max_radius_km": _round(max_radius, 3),
        },
    }
    recommended_plan = {
        "plan_id": "plan_priority_containment_recon",
        "name": "Downwind reconnaissance and protected-target pre-positioning",
        "score": 91 if risk_level == "high" else 84 if risk_level == "medium" else 76,
        "strategy": "Use the trusted fire point as the decision anchor; verify downwind fireline growth, pre-position protected-target resources, and keep evacuation routes available.",
        "reasons": [
            f"Projected final area: {final_area:.2f} km2",
            f"Wind speed {env.wind_speed_m_s:.1f} m/s, direction {env.wind_direction_deg:.0f} deg",
            f"Fire weather index {env.fire_weather_index:.1f}",
        ],
    }
    uav_tasks = [
        {
            "task_id": "uav_recon_downwind_01",
            "owner": "UAV Team 1",
            "action": "Run thermal-infrared verification along the downwind fireline.",
            "target": "Downwind area within about 1.5 km of the trusted fire point",
            "priority": "critical" if risk_level == "high" else "high",
            "reason": "Confirm fireline boundary and return visual/thermal evidence.",
        },
        {
            "task_id": "uav_route_watch_02",
            "owner": "UAV Team 2",
            "action": "Inspect primary and backup evacuation corridors.",
            "target": "Routes from protected targets to safe assembly points",
            "priority": "high",
            "reason": "Support route package with current passability evidence.",
        },
    ]
    route_options = [
        {
            "route_id": "main_evacuation",
            "name": "Primary evacuation route",
            "type": "evacuation",
            "risk": "safe",
            "summary": "Avoid the downwind expansion sector and prioritize existing main roads.",
            "reason": "Keeps safe distance from projected fireline.",
        },
        {
            "route_id": "backup_evacuation",
            "name": "Backup evacuation route",
            "type": "backup",
            "risk": "moderate",
            "summary": "Switch to lateral road access when the primary corridor is blocked.",
            "reason": "Supports replanning under road-unavailable conditions.",
        },
        {
            "route_id": "rescue_approach",
            "name": "Rescue approach route",
            "type": "rescue_approach",
            "risk": "moderate",
            "summary": "Approach from the upwind/sidewind direction and avoid crossing the projected fireline.",
            "reason": "Reduces exposure risk for personnel and vehicles.",
        },
    ]
    dispatch_tasks = [
        {
            "task_id": "resource_forward_command",
            "owner": "Forward Command Team",
            "action": "Set up temporary command and communications node.",
            "target": "Upwind safe area near the trusted fire point",
            "priority": "critical" if risk_level == "high" else "high",
            "reason": "Support multi-source situational awareness, UAV return feed, and route coordination.",
        },
        {
            "task_id": "resource_protection_targets",
            "owner": "Resource Dispatch Team",
            "action": "Pre-position personnel and equipment around protected targets.",
            "target": "Downwind settlements or forest-edge protected targets",
            "priority": "high",
            "reason": "Cover likely high-risk spread direction early.",
        },
    ]
    dispatch_zones = _dispatch_zones(trusted, env, max_radius, risk_level)
    packages = {
        "situation_packet": situation_packet,
        "risk_packet": risk_packet,
        "plan_packet": {
            "recommended_plan": recommended_plan,
            "candidate_plans": [
                recommended_plan,
                {"plan_id": "plan_recon_first", "name": "Reconnaissance-first plan", "score": max(60, recommended_plan["score"] - 7)},
                {"plan_id": "plan_resource_forward", "name": "Resource-forward plan", "score": max(60, recommended_plan["score"] - 10)},
            ],
        },
        "recommendation_packet": {
            "summary": llm_text,
            "recommended_plan": recommended_plan,
            "warnings": warnings,
        },
        "uav_recommendation_packet": {
            "summary": "Prioritize downwind fireline verification and route passability inspection.",
            "uav_tasks": uav_tasks,
            "tasks": uav_tasks,
        },
        "route_recommendation_packet": {
            "summary": "Provide primary, backup, and rescue-approach route options.",
            "route_options": route_options,
            "evacuation_routes": route_options,
        },
        "resource_recommendation_packet": {
            "summary": "Prioritize command communications, protected-target pre-positioning, and UAV-supported reconnaissance.",
            "dispatch_tasks": dispatch_tasks,
            "dispatch_zones": dispatch_zones,
            "summary_numbers": {"personnel": 48, "uavs": len(uav_tasks), "vehicles": 8},
        },
        "report_packet": {
            "title": "Early Fire Command Decision Report",
            "summary": llm_text,
            "input_summary": input_summary,
            "generated_by": {"provider": provider, "model": model},
        },
    }
    return input_summary, packages, warnings

async def create_decision_run(db: AsyncSession, event_id: str, request: DecisionRunRequest) -> dict[str, Any]:
    event = await get_event_or_404(db, event_id)
    trusted = await _latest(db, TrustedFirePoint, event_id)
    if not trusted:
        raise AppError("Trusted fire point is required before decision run.", code="trusted_point_required", status_code=400)
    env = await _latest(db, EnvironmentSnapshot, event_id)
    if not env:
        raise AppError("Environment snapshot is required before decision run.", code="environment_required", status_code=400)
    spread = await _latest(db, SimulationRun, event_id)
    if not spread:
        raise AppError("Spread run is required before decision run.", code="spread_run_required", status_code=400)
    fusion = await _latest(db, FusionResult, event_id)
    steps = await _spread_steps(db, spread.run_id)
    provider = get_llm_provider(request.force_provider)
    preliminary_summary = {
        "input_summary": {
            "final_area_km2": spread.final_area_km2,
            "risk_level": spread.risk_level,
            "wind_speed_m_s": env.wind_speed_m_s,
            "fire_weather_index": env.fire_weather_index,
        }
    }
    llm = await provider.generate(
        "You are an early wildfire command decision agent. Explain only the structured tool results and do not invent numeric values.",
        preliminary_summary,
    )
    decision_run_id = f"dec_{uuid4().hex[:18]}"
    input_summary, packages, warnings = _build_packets(
        decision_run_id=decision_run_id,
        event_id=event_id,
        event_name=event.name,
        provider=llm.provider,
        model=llm.model,
        trusted=trusted,
        fusion=fusion,
        env=env,
        spread=spread,
        steps=steps,
        llm_text=llm.content,
    )
    confidence = min(0.96, max(0.55, float(input_summary["fusion_confidence"]) * 0.45 + (0.42 if steps else 0.25)))
    run = DecisionRun(
        decision_run_id=decision_run_id,
        event_id=event_id,
        scenario_id=event.scenario_id,
        status="completed",
        provider=llm.provider,
        model=llm.model,
        confidence=_round(confidence, 3),
        recommended_plan=packages["plan_packet"]["recommended_plan"],
        input_summary=input_summary,
        warnings=warnings,
        raw_llm_output=llm.content,
    )
    db.add(run)
    await db.flush()
    packets: list[AgentPacket] = []
    titles = {
        "situation_packet": "Environment Agent situation packet",
        "risk_packet": "Spread Agent risk packet",
        "plan_packet": "Command Agent plan packet",
        "recommendation_packet": "Integrated recommendation packet",
        "uav_recommendation_packet": "UAV recommendation packet",
        "route_recommendation_packet": "Route recommendation packet",
        "resource_recommendation_packet": "Resource dispatch recommendation packet",
        "report_packet": "Early command report packet",
    }
    for packet_type in PACKET_TYPES:
        packet = AgentPacket(
            packet_id=f"pkt_{uuid4().hex}",
            decision_run_id=decision_run_id,
            event_id=event_id,
            packet_type=packet_type,
            title=titles[packet_type],
            content=packages[packet_type],
        )
        db.add(packet)
        packets.append(packet)
    await append_timeline(
        db,
        event_id=event_id,
        event_type="decision.completed",
        status="deciding",
        title="Decision run completed",
        message="Multi-agent command decision packets have been generated.",
        payload={
            "decision_run_id": decision_run_id,
            "provider": llm.provider,
            "model": llm.model,
            "packet_count": len(packets),
            "recommended_plan": run.recommended_plan,
        },
        broadcast=True,
    )
    await db.commit()
    await db.refresh(run)
    for packet in packets:
        await db.refresh(packet)
    await websocket_manager.broadcast_event(
        event_id,
        "decision.completed",
        {"decision_run_id": decision_run_id, "provider": llm.provider, "model": llm.model, "packages": packages},
    )
    return {"run": run, "packets": packets, "packages": packages}


async def latest_decision_run(db: AsyncSession, event_id: str) -> dict[str, Any] | None:
    await get_event_or_404(db, event_id)
    result = await db.execute(
        select(DecisionRun).where(DecisionRun.event_id == event_id).order_by(desc(DecisionRun.created_at), desc(DecisionRun.id)).limit(1)
    )
    run = result.scalar_one_or_none()
    if not run:
        return None
    packets = await decision_packets(db, run.decision_run_id)
    packages = {packet.packet_type: packet.content for packet in packets}
    return {"run": run, "packets": packets, "packages": packages}


async def decision_packets(db: AsyncSession, decision_run_id: str) -> list[AgentPacket]:
    result = await db.execute(
        select(AgentPacket).where(AgentPacket.decision_run_id == decision_run_id).order_by(AgentPacket.id)
    )
    return list(result.scalars().all())



