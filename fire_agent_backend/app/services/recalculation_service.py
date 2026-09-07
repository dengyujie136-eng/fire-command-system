from copy import deepcopy
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.recalculation import RecalculationRun, ScenarioDisturbance
from app.models.recommendation import RecommendationPackage, ResourceInventory, RoutePlan, UavAsset
from app.schemas.recalculation import RecalculationRequest, ScenarioDisturbanceCreate
from app.services.event_service import append_timeline, get_event_or_404
from app.services.recommendation_service import latest_recommendations, regenerate_recommendations
from app.schemas.recommendation import RecommendationRegenerateRequest
from app.services.websocket_manager import websocket_manager


def _read_model(item: Any) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for key in item.__mapper__.columns.keys():
        data[key] = getattr(item, key)
    return data


def _snapshot(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    package = payload["package"]
    return {
        "package_id": package.package_id,
        "status": package.status,
        "summary": package.summary,
        "route_count": len(payload.get("routes") or []),
        "uav_count": len(payload.get("uavs") or []),
        "resource_count": len(payload.get("resources") or []),
        "route_package": deepcopy(package.route_package),
        "uav_package": deepcopy(package.uav_package),
        "resource_package": deepcopy(package.resource_package),
        "command_package": deepcopy(package.command_package),
    }


def _route_blocked(route: dict[str, Any], parameters: dict[str, Any]) -> bool:
    blocked_id = parameters.get("route_id") or parameters.get("blocked_route_id")
    blocked_type = parameters.get("route_type") or parameters.get("blocked_route_type")
    blocked_name = str(parameters.get("route_name") or parameters.get("blocked_route_name") or "").lower()
    if blocked_id and route.get("route_id") == blocked_id:
        return True
    if blocked_type and (route.get("type") == blocked_type or route.get("route_type") == blocked_type):
        return True
    if blocked_name and blocked_name in str(route.get("name") or "").lower():
        return True
    return not any([blocked_id, blocked_type, blocked_name]) and route.get("type") in {"evacuation", "main_evacuation"}


def _apply_wind_shift(package: dict[str, Any], parameters: dict[str, Any]) -> dict[str, Any]:
    degree = parameters.get("wind_direction_deg") or parameters.get("new_wind_direction_deg") or parameters.get("shift_degrees") or 45
    package["summary"] = f"Wind shift assumption applied: command recommendations now prioritize cross-wind evacuation and renewed UAV fireline verification."
    route_package = package["route_package"]
    uav_package = package["uav_package"]
    resource_package = package["resource_package"]
    route_package["summary"] = f"Wind shift to {degree} degrees requires avoiding the new downwind sector and preferring cross-wind routes."
    for index, route in enumerate(route_package.get("route_options") or []):
        route["risk"] = "elevated" if index == 0 else route.get("risk", "moderate")
        route["summary"] = f"{route.get('summary', 'Route')} Rechecked against shifted wind direction {degree} degrees."
        route["reason"] = "Wind-shift recalculation changed the exposure sector."
    for task in uav_package.get("uav_tasks") or []:
        task["priority"] = "critical"
        task["action"] = "Reconfirm fireline and smoke drift after wind shift"
        task["reason"] = f"New assumed wind direction is {degree} degrees."
    resource_package["summary"]["weather_recheck_required"] = True
    package["command_package"]["summary"] = route_package["summary"]
    return {
        "type": "wind_shift",
        "message": "Wind-shift assumption changed route risk and UAV reconnaissance priority.",
        "wind_direction_deg": degree,
    }


def _apply_road_unavailable(package: dict[str, Any], parameters: dict[str, Any]) -> dict[str, Any]:
    route_package = package["route_package"]
    changed_routes: list[str] = []
    for route in route_package.get("route_options") or []:
        if _route_blocked(route, parameters):
            route["risk"] = "blocked"
            route["status"] = "unavailable"
            route["summary"] = f"{route.get('name', 'Route')} is excluded by the road-unavailable assumption."
            route["reason"] = "Command-side what-if assumption marked this route unavailable."
            changed_routes.append(route.get("route_id") or route.get("name") or "route")
        elif changed_routes and route.get("type") in {"backup", "rescue_approach"}:
            route["risk"] = "preferred"
            route["summary"] = f"{route.get('summary', 'Route')} Elevated as fallback after road unavailability."
    route_package["summary"] = "Road-unavailable assumption applied: blocked route is excluded and backup route is promoted."
    package["command_package"]["summary"] = route_package["summary"]
    package["command_package"]["route_change"] = {"blocked_routes": changed_routes, "fallback_required": True}
    return {
        "type": "road_unavailable",
        "message": "Road-unavailable assumption changed primary/backup route ordering.",
        "blocked_routes": changed_routes,
    }


def _apply_uav_reduced(package: dict[str, Any], parameters: dict[str, Any]) -> dict[str, Any]:
    available = int(parameters.get("available_uavs") or parameters.get("available_count") or 1)
    uav_package = package["uav_package"]
    tasks = uav_package.get("uav_tasks") or []
    for index, task in enumerate(tasks):
        if index >= available:
            task["status"] = "held"
            task["priority"] = "deferred"
            task["reason"] = "UAV availability reduction assumption holds this task."
    uav_package["summary"] = f"UAV availability reduced to {available}; high-priority reconnaissance is retained first."
    package["command_package"]["uav"] = {"online": available, "mission": min(available, len(tasks))}
    return {"type": "uav_availability_reduced", "message": "UAV mission list was reprioritized.", "available_uavs": available}


def _apply_protected_target_priority(package: dict[str, Any], parameters: dict[str, Any]) -> dict[str, Any]:
    target = parameters.get("target") or parameters.get("target_name") or "priority protected target"
    resource_package = package["resource_package"]
    for task in resource_package.get("dispatch_tasks") or []:
        task["priority"] = "critical"
        task["target"] = target
        task["reason"] = f"Protected target priority changed to {target}."
    resource_package["summary"]["priority_target"] = target
    package["command_package"]["summary"] = f"Protected target priority changed to {target}; resources are concentrated around that target."
    return {"type": "protected_target_priority_changed", "message": "Resource allocation was shifted to the protected target.", "target": target}


def _apply_weather_risk(package: dict[str, Any], parameters: dict[str, Any]) -> dict[str, Any]:
    level = parameters.get("risk_level") or "high"
    route_package = package["route_package"]
    resource_package = package["resource_package"]
    for route in route_package.get("route_options") or []:
        if route.get("risk") not in {"blocked", "unavailable"}:
            route["risk"] = "elevated"
            route["reason"] = "Weather-risk increase assumption raised exposure level."
    resource_package["summary"]["weather_risk_level"] = level
    package["command_package"]["summary"] = f"Weather risk increased to {level}; route risk and resource standby level were raised."
    return {"type": "weather_risk_increased", "message": "Weather-risk assumption raised route and resource risk posture.", "risk_level": level}


def _apply_disturbance(base_payload: dict[str, Any], disturbance: ScenarioDisturbance) -> tuple[dict[str, Any], dict[str, Any]]:
    package = base_payload["package"]
    mutable = {
        "summary": package.summary,
        "route_package": deepcopy(package.route_package),
        "uav_package": deepcopy(package.uav_package),
        "resource_package": deepcopy(package.resource_package),
        "command_package": deepcopy(package.command_package),
    }
    parameters = disturbance.parameters or {}
    handlers = {
        "wind_shift": _apply_wind_shift,
        "road_unavailable": _apply_road_unavailable,
        "uav_availability_reduced": _apply_uav_reduced,
        "protected_target_priority_changed": _apply_protected_target_priority,
        "weather_risk_increased": _apply_weather_risk,
    }
    change = handlers[disturbance.disturbance_type](mutable, parameters)
    mutable["command_package"]["disturbance"] = {
        "disturbance_id": disturbance.disturbance_id,
        "type": disturbance.disturbance_type,
        "assumption": disturbance.assumption,
        "parameters": parameters,
    }
    mutable["summary"] = mutable["command_package"].get("summary") or mutable["summary"]
    return mutable, change


async def create_disturbance(db: AsyncSession, event_id: str, request: ScenarioDisturbanceCreate) -> ScenarioDisturbance:
    await get_event_or_404(db, event_id)
    disturbance = ScenarioDisturbance(
        disturbance_id=f"dst_{uuid4().hex[:18]}",
        event_id=event_id,
        disturbance_type=request.disturbance_type,
        assumption=request.assumption,
        parameters=request.parameters,
        created_by=request.created_by,
    )
    db.add(disturbance)
    await append_timeline(
        db,
        event_id=event_id,
        event_type="disturbance.created",
        status="what_if",
        title="What-if disturbance created",
        message=f"Command-side assumption recorded: {request.disturbance_type}.",
        payload={"disturbance_id": disturbance.disturbance_id, "type": request.disturbance_type},
        broadcast=True,
    )
    await db.commit()
    await db.refresh(disturbance)
    await websocket_manager.broadcast_event(event_id, "disturbance.created", {"disturbance_id": disturbance.disturbance_id})
    return disturbance


async def _get_disturbance(db: AsyncSession, event_id: str, disturbance_id: str) -> ScenarioDisturbance:
    result = await db.execute(
        select(ScenarioDisturbance)
        .where(ScenarioDisturbance.event_id == event_id, ScenarioDisturbance.disturbance_id == disturbance_id)
        .limit(1)
    )
    disturbance = result.scalar_one_or_none()
    if not disturbance:
        raise AppError(f"Disturbance not found: {disturbance_id}", code="disturbance_not_found", status_code=404)
    return disturbance


async def recalculate(db: AsyncSession, event_id: str, request: RecalculationRequest) -> dict[str, Any]:
    await get_event_or_404(db, event_id)
    if request.disturbance_id:
        disturbance = await _get_disturbance(db, event_id, request.disturbance_id)
    elif request.disturbance:
        disturbance = await create_disturbance(db, event_id, request.disturbance)
    else:
        raise AppError("Either disturbance_id or disturbance must be provided.", code="disturbance_required", status_code=400)

    base_payload = await latest_recommendations(db, event_id)
    if not base_payload:
        base_payload = await regenerate_recommendations(db, event_id, RecommendationRegenerateRequest(status=request.status))
    before = _snapshot(base_payload)
    new_package, change_summary = _apply_disturbance(base_payload, disturbance)

    package_id = f"rec_{uuid4().hex[:18]}"
    base_package = base_payload["package"]
    rec = RecommendationPackage(
        package_id=package_id,
        event_id=event_id,
        decision_run_id=base_package.decision_run_id,
        status=request.status,
        summary=new_package["summary"],
        route_package=new_package["route_package"],
        uav_package=new_package["uav_package"],
        resource_package=new_package["resource_package"],
        command_package=new_package["command_package"],
    )
    db.add(rec)
    await db.flush()

    routes = new_package["route_package"].get("route_options") or []
    uavs = new_package["uav_package"].get("uav_tasks") or []
    resources = new_package["resource_package"].get("dispatch_tasks") or []
    for index, route in enumerate(routes):
        route_id = route.get("route_id") or f"route_{index + 1}"
        db.add(
            RoutePlan(
                route_id=f"{package_id}_{route_id}_{index}",
                package_id=package_id,
                event_id=event_id,
                name=route.get("name") or f"Route {index + 1}",
                route_type=route.get("type") or route.get("route_type") or route_id,
                risk=route.get("risk") or "moderate",
                summary=route.get("summary") or "",
                geometry=route.get("geometry") or {},
                metadata_json={"reason": route.get("reason") or "", "status": route.get("status") or request.status},
            )
        )
    for index, task in enumerate(uavs):
        uav_id = task.get("uav_id") or f"UAV-{index + 1:02d}"
        db.add(
            UavAsset(
                asset_id=f"{package_id}_{uav_id}_{index}",
                package_id=package_id,
                event_id=event_id,
                name=task.get("name") or uav_id,
                status=task.get("status") or request.status,
                task=task,
                longitude=float(task.get("longitude") or 0),
                latitude=float(task.get("latitude") or 0),
                metadata_json={"priority": task.get("priority"), "reason": task.get("reason")},
            )
        )
    for index, resource in enumerate(resources):
        resource_id = resource.get("resource_id") or resource.get("task_id") or f"resource_{index + 1}"
        db.add(
            ResourceInventory(
                resource_id=f"{package_id}_{resource_id}_{index}",
                package_id=package_id,
                event_id=event_id,
                resource_type=resource.get("resource_type") or resource.get("type") or "command_resource",
                name=resource.get("name") or resource.get("owner") or f"Resource {index + 1}",
                quantity=int(resource.get("quantity") or 0),
                unit=resource.get("unit") or "",
                status=resource.get("status") or request.status,
                target=resource.get("target") or "",
                metadata_json={"task": resource},
            )
        )

    after = {
        "package_id": package_id,
        "status": request.status,
        "summary": new_package["summary"],
        "route_count": len(routes),
        "uav_count": len(uavs),
        "resource_count": len(resources),
        "route_package": deepcopy(new_package["route_package"]),
        "uav_package": deepcopy(new_package["uav_package"]),
        "resource_package": deepcopy(new_package["resource_package"]),
        "command_package": deepcopy(new_package["command_package"]),
    }
    recalculation = RecalculationRun(
        recalculation_id=f"rcl_{uuid4().hex[:18]}",
        event_id=event_id,
        disturbance_id=disturbance.disturbance_id,
        status="completed",
        base_package_id=before.get("package_id", ""),
        new_package_id=package_id,
        change_summary=change_summary,
        before_snapshot=before,
        after_snapshot=after,
    )
    db.add(recalculation)
    await append_timeline(
        db,
        event_id=event_id,
        event_type="recalculation.completed",
        status="recommended",
        title="What-if recalculation completed",
        message=f"Recommendations recalculated for {disturbance.disturbance_type}.",
        payload={"recalculation_id": recalculation.recalculation_id, "package_id": package_id, "change_summary": change_summary},
        broadcast=True,
    )
    await db.commit()
    await db.refresh(recalculation)
    payload = await latest_recalculation(db, event_id)
    await websocket_manager.broadcast_event(
        event_id,
        "recalculation.completed",
        {"recalculation_id": recalculation.recalculation_id, "package_id": package_id, "change_summary": change_summary},
    )
    return payload


async def latest_recalculation(db: AsyncSession, event_id: str) -> dict[str, Any] | None:
    await get_event_or_404(db, event_id)
    result = await db.execute(
        select(RecalculationRun)
        .where(RecalculationRun.event_id == event_id)
        .order_by(desc(RecalculationRun.created_at), desc(RecalculationRun.id))
        .limit(1)
    )
    recalculation = result.scalar_one_or_none()
    if not recalculation:
        return None
    disturbance = await _get_disturbance(db, event_id, recalculation.disturbance_id)
    recommendation = await latest_recommendations(db, event_id)
    return {
        "disturbance": disturbance,
        "recalculation": recalculation,
        "recommendation": recommendation,
    }
