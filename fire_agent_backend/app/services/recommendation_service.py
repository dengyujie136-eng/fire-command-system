from typing import Any
from uuid import uuid4

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.decision import DecisionRun
from app.models.event import FireEvent
from app.models.recommendation import RecommendationPackage, ResourceInventory, RoutePlan, UavAsset
from app.schemas.decision import DecisionRunRequest
from app.schemas.recommendation import RecommendationRegenerateRequest
from app.services.decision_service import create_decision_run, latest_decision_run
from app.services.event_service import append_timeline, get_event_or_404
from app.services.websocket_manager import websocket_manager


def _point(lng: float, lat: float, name: str) -> dict[str, Any]:
    return {"name": name, "longitude": round(lng, 7), "latitude": round(lat, 7)}


def _line(points: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "LineString",
        "coordinates": [[point["longitude"], point["latitude"]] for point in points],
    }


def _route_geometry(event: FireEvent, index: int) -> dict[str, Any]:
    lng = event.ignition_longitude
    lat = event.ignition_latitude
    offsets = [
        [(-0.020, -0.012), (-0.038, -0.025)],
        [(-0.018, 0.010), (-0.035, 0.018)],
        [(0.012, -0.018), (0.026, -0.034)],
    ][index % 3]
    points = [
        _point(lng, lat, "可信火点"),
        _point(lng + offsets[0][0], lat + offsets[0][1], "路线控制点"),
        _point(lng + offsets[1][0], lat + offsets[1][1], "安全集结点"),
    ]
    return {"points": points, "geojson": _line(points)}


def _normalize_route(route: dict[str, Any], event: FireEvent, index: int) -> dict[str, Any]:
    geometry = route.get("geometry") or _route_geometry(event, index)
    route_id = route.get("route_id") or route.get("id") or f"route_{index + 1}"
    route_type = route.get("type") or route.get("route_type") or route_id
    return {
        "route_id": route_id,
        "name": route.get("name") or route.get("route_name") or f"推荐路线 {index + 1}",
        "type": route_type,
        "risk": route.get("risk") or route.get("riskClass") or "moderate",
        "summary": route.get("summary") or route.get("desc") or route.get("reason") or "Agent 推荐路线",
        "reason": route.get("reason") or route.get("summary") or "根据火势、风向和保护目标生成",
        "geometry": geometry,
    }


def _normalize_uav(task: dict[str, Any], event: FireEvent, index: int) -> dict[str, Any]:
    lng = float(task.get("longitude") or task.get("lng") or event.ignition_longitude + 0.004 * (index + 1))
    lat = float(task.get("latitude") or task.get("lat") or event.ignition_latitude + 0.003 * (index + 1))
    task_id = task.get("task_id") or f"uav_task_{index + 1}"
    return {
        "task_id": task_id,
        "uav_id": task.get("uav_id") or f"UAV-{index + 1:02d}",
        "name": task.get("name") or task.get("owner") or f"无人机 {index + 1:02d}",
        "action": task.get("action") or "执行火线复核",
        "target": task.get("target") or "下风向火线",
        "priority": task.get("priority") or "high",
        "reason": task.get("reason") or "补充空中态势证据",
        "longitude": lng,
        "latitude": lat,
        "status": task.get("status") or "recommended",
    }


def _normalize_resource(task: dict[str, Any], index: int) -> dict[str, Any]:
    task_id = task.get("task_id") or f"resource_task_{index + 1}"
    return {
        "resource_id": task_id,
        "resource_type": task.get("resource_type") or task.get("type") or "command_resource",
        "name": task.get("owner") or task.get("name") or f"推荐资源 {index + 1}",
        "quantity": int(task.get("quantity") or task.get("amount") or (24 if index == 0 else 12)),
        "unit": task.get("unit") or ("人" if index == 0 else "组"),
        "target": task.get("target") or task.get("location") or "保护目标前置点",
        "status": task.get("status") or "recommended",
        "task": task,
    }


def _packages_from_decision(decision_data: dict[str, Any]) -> dict[str, Any]:
    packages = decision_data.get("packages") or {}
    route_package = packages.get("route_recommendation_packet") or packages.get("route_package") or {}
    uav_package = packages.get("uav_recommendation_packet") or packages.get("uav_package") or {}
    resource_package = packages.get("resource_recommendation_packet") or packages.get("resource_package") or {}
    command_package = {
        "recommended_plan": decision_data.get("run").recommended_plan,
        "summary": packages.get("recommendation_packet", {}).get("summary") or route_package.get("summary") or "",
        "uav": {"online": len(uav_package.get("uav_tasks") or uav_package.get("tasks") or [])},
        "resources": resource_package.get("summary_numbers") or {},
        "personnel": {"total": resource_package.get("summary_numbers", {}).get("personnel", 0), "deployed": resource_package.get("summary_numbers", {}).get("personnel", 0)},
        "vehicles": {"total": resource_package.get("summary_numbers", {}).get("vehicles", 0), "deployed": resource_package.get("summary_numbers", {}).get("vehicles", 0)},
        "evacuation": {"people": 0},
    }
    return {
        "route_package": route_package,
        "uav_package": uav_package,
        "resource_package": resource_package,
        "command_package": command_package,
    }


async def regenerate_recommendations(db: AsyncSession, event_id: str, request: RecommendationRegenerateRequest) -> dict[str, Any]:
    event = await get_event_or_404(db, event_id)
    decision_data = await latest_decision_run(db, event_id)
    if not decision_data:
        decision_data = await create_decision_run(db, event_id, DecisionRunRequest())
    run: DecisionRun = decision_data["run"]
    package_id = f"rec_{uuid4().hex[:18]}"
    normalized = _packages_from_decision(decision_data)
    route_package = dict(normalized["route_package"])
    uav_package = dict(normalized["uav_package"])
    resource_package = dict(normalized["resource_package"])
    command_package = dict(normalized["command_package"])

    raw_routes = [
        *(route_package.get("route_options") or []),
        *(route_package.get("evacuation_routes") or []),
        *(route_package.get("rescue_routes") or []),
    ]
    if not raw_routes:
        raise AppError("Decision run does not contain route recommendations.", code="route_recommendations_missing", status_code=400)
    routes = [_normalize_route(route, event, index) for index, route in enumerate(raw_routes[:3])]
    route_package["route_options"] = routes
    route_package["evacuation_routes"] = routes
    route_package.setdefault("entry_point", _point(event.ignition_longitude, event.ignition_latitude, "可信火点"))
    route_package.setdefault("safe_assembly_point", routes[0]["geometry"]["points"][-1])

    raw_uavs = uav_package.get("uav_tasks") or uav_package.get("tasks") or []
    uavs = [_normalize_uav(task, event, index) for index, task in enumerate(raw_uavs[:4])]
    uav_package["uav_tasks"] = uavs
    uav_package["tasks"] = uavs
    uav_package["summary"] = uav_package.get("summary") or "已生成无人机侦察推荐任务"

    raw_resources = resource_package.get("dispatch_tasks") or resource_package.get("tasks") or []
    resources = [_normalize_resource(task, index) for index, task in enumerate(raw_resources[:5])]
    resource_package["dispatch_tasks"] = resources
    resource_package["tasks"] = resources
    resource_package["summary"] = {
        "personnel": sum(item["quantity"] for item in resources if item["unit"] == "人") or resource_package.get("summary_numbers", {}).get("personnel", 0),
        "uavs": len(uavs),
        "vehicles": resource_package.get("summary_numbers", {}).get("vehicles", 0),
        "resource_points": len(resources),
        "route_length_km": round(len(routes) * 6.5, 1),
    }
    command_package["resources"] = resource_package["summary"]
    command_package["uav"] = {"online": len(uavs), "mission": len(uavs)}

    rec = RecommendationPackage(
        package_id=package_id,
        event_id=event_id,
        decision_run_id=run.decision_run_id,
        status=request.status,
        summary=command_package.get("summary") or route_package.get("summary") or "已生成路线、无人机与资源推荐包",
        route_package=route_package,
        uav_package=uav_package,
        resource_package=resource_package,
        command_package=command_package,
    )
    db.add(rec)
    await db.flush()

    for index, route in enumerate(routes):
        db.add(
            RoutePlan(
                route_id=f"{package_id}_{route['route_id']}_{index}",
                package_id=package_id,
                event_id=event_id,
                name=route["name"],
                route_type=route["type"],
                risk=route["risk"],
                summary=route["summary"],
                geometry=route["geometry"],
                metadata_json={"reason": route["reason"], "status": request.status},
            )
        )
    for index, uav in enumerate(uavs):
        db.add(
            UavAsset(
                asset_id=f"{package_id}_{uav['uav_id']}_{index}",
                package_id=package_id,
                event_id=event_id,
                name=uav["name"],
                status=request.status,
                task=uav,
                longitude=uav["longitude"],
                latitude=uav["latitude"],
                metadata_json={"priority": uav["priority"], "reason": uav["reason"]},
            )
        )
    for index, resource in enumerate(resources):
        db.add(
            ResourceInventory(
                resource_id=f"{package_id}_{resource['resource_id']}_{index}",
                package_id=package_id,
                event_id=event_id,
                resource_type=resource["resource_type"],
                name=resource["name"],
                quantity=resource["quantity"],
                unit=resource["unit"],
                status=request.status,
                target=resource["target"],
                metadata_json={"task": resource["task"]},
            )
        )
    await append_timeline(
        db,
        event_id=event_id,
        event_type="recommendations.generated",
        status=request.status,
        title="Recommendation package generated",
        message="Route, UAV, and resource recommendation packages have been stored for command review.",
        payload={"package_id": package_id, "decision_run_id": run.decision_run_id, "status": request.status},
        broadcast=True,
    )
    await db.commit()
    await db.refresh(rec)
    payload = await latest_recommendations(db, event_id)
    await websocket_manager.broadcast_event(event_id, "recommendations.generated", {"package_id": package_id, "status": request.status})
    return payload


async def latest_recommendations(db: AsyncSession, event_id: str) -> dict[str, Any] | None:
    await get_event_or_404(db, event_id)
    result = await db.execute(
        select(RecommendationPackage)
        .where(RecommendationPackage.event_id == event_id, RecommendationPackage.status != "archived")
        .order_by(desc(RecommendationPackage.created_at), desc(RecommendationPackage.id))
        .limit(1)
    )
    package = result.scalar_one_or_none()
    if not package:
        return None
    route_result = await db.execute(select(RoutePlan).where(RoutePlan.package_id == package.package_id).order_by(RoutePlan.id))
    uav_result = await db.execute(select(UavAsset).where(UavAsset.package_id == package.package_id).order_by(UavAsset.id))
    resource_result = await db.execute(select(ResourceInventory).where(ResourceInventory.package_id == package.package_id).order_by(ResourceInventory.id))
    return {
        "package": package,
        "routes": list(route_result.scalars().all()),
        "uavs": list(uav_result.scalars().all()),
        "resources": list(resource_result.scalars().all()),
    }
