"""Deterministic resource dispatch calculation for wildfire response tasks."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable

from app.services.resources.models import (
    DispatchStrategy,
    Resource,
    ResourceDispatchResult,
    ResourceRequirement,
    ResourceTask,
)
from app.services.routing import RoadNetwork, RouteResult, RoutingRequest, VehicleProfile, calculate_route

DEFAULT_AIR_SPEED_KMH = 72.0


_DEFAULT_TASK_REQUIREMENTS: dict[str, tuple[ResourceRequirement, ...]] = {
    "fire_suppression": (
        ResourceRequirement("fire_engine", 1, frozenset({"fire_suppression"})),
        ResourceRequirement("fire_team", 1, frozenset({"fire_suppression", "handline"})),
    ),
    "structure_protection": (
        ResourceRequirement("fire_engine", 1, frozenset({"structure_protection"})),
        ResourceRequirement("fire_team", 1, frozenset({"structure_protection"})),
    ),
    "reconnaissance": (ResourceRequirement("uav", 1, frozenset({"aerial_recon"})),),
    "evacuation_support": (
        ResourceRequirement("evacuation_support", 1, frozenset({"evacuation_support"})),
    ),
}


def calculate_resource_dispatch(
    task: ResourceTask,
    resources: Iterable[Resource],
    road_network: RoadNetwork,
) -> ResourceDispatchResult:
    """Evaluate and greedily allocate real inventory against one emergency task."""
    _validate_strategy(task.strategy)
    road_network.node(task.target_node_id)
    inventory = list(resources)
    requirements = _requirements(task)
    evaluations = [_evaluate_resource(task, requirement, resource, road_network) for resource in inventory for requirement in requirements]
    _score_candidates(task.strategy, evaluations)

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    shortages: list[dict[str, Any]] = []

    for requirement in requirements:
        matching = [
            evaluation
            for evaluation in evaluations
            if evaluation["requirement"]["resource_type"] == requirement.resource_type
            and evaluation["status"] == "candidate"
            and evaluation["resource_id"] not in selected_ids
        ]
        matching.sort(key=lambda item: (-float(item["score"]), item["estimated_response_minutes"], item["resource_id"]))
        allocated = matching[: max(0, requirement.quantity)]
        for evaluation in allocated:
            evaluation["status"] = "selected"
            evaluation["assigned_task"] = task.task_id
            evaluation["reason_codes"].append("selected_for_requirement")
            selected_ids.add(evaluation["resource_id"])
            selected.append(evaluation)
        if len(allocated) < requirement.quantity:
            shortages.append(
                {
                    "resource_type": requirement.resource_type,
                    "requested": requirement.quantity,
                    "allocated": len(allocated),
                    "shortage": requirement.quantity - len(allocated),
                    "required_capabilities": sorted(_required_capabilities(task, requirement)),
                    "reason_code": "insufficient_available_resources",
                }
            )

    candidates = [evaluation for evaluation in evaluations if evaluation["status"] in {"candidate", "selected"}]
    rejected = [evaluation for evaluation in evaluations if evaluation["status"] == "rejected"]
    warnings = _warnings(shortages, rejected)
    estimated_response = _estimated_response(selected)
    status = "success" if not shortages else "partial" if selected else "failed"
    return ResourceDispatchResult(
        success=not shortages,
        status=status,
        task=_task_summary(task, requirements),
        strategy=task.strategy,
        selected_resources=selected,
        candidate_resources=candidates,
        rejected_resources=rejected,
        resource_shortage=shortages,
        total_resource_count=len(inventory),
        estimated_response=estimated_response,
        warnings=warnings,
        metadata={
            "calculation_unit": "Resource Calculation Unit",
            "routing_unit_used": True,
            "llm_used": False,
            "requirement_count": len(requirements),
        },
    )


def _validate_strategy(strategy: str) -> None:
    if strategy not in {"fastest_response", "safest_response", "capability_first", "balanced"}:
        raise ValueError(f"Unsupported dispatch strategy: {strategy}")


def _requirements(task: ResourceTask) -> tuple[ResourceRequirement, ...]:
    if task.minimum_resource_requirements:
        return task.minimum_resource_requirements
    return _DEFAULT_TASK_REQUIREMENTS.get(task.task_type, tuple())


def _evaluate_resource(
    task: ResourceTask,
    requirement: ResourceRequirement,
    resource: Resource,
    road_network: RoadNetwork,
) -> dict[str, Any]:
    base = {
        "resource_id": resource.resource_id,
        "resource_type": resource.resource_type,
        "name": resource.name,
        "assigned_task": None,
        "requirement": _requirement_summary(task, requirement),
        "resource": resource.to_summary(),
        "origin": _origin(resource, road_network),
        "target": road_network.node(task.target_node_id).to_point(),
        "status": "rejected",
        "capability_match": False,
        "capability_score": 0.0,
        "route_status": "not_evaluated",
        "estimated_response_minutes": None,
        "risk_score": None,
        "distance_km": None,
        "route": None,
        "terrain_metrics": {},
        "road_metrics": {},
        "accessibility": {},
        "score": 0.0,
        "reason_codes": [],
        "diagnostics": {},
    }

    if resource.resource_type != requirement.resource_type:
        base["reason_codes"].append("resource_type_not_required")
        return base
    if not resource.is_available():
        base["reason_codes"].append("unavailable")
        return base

    capability = _capability_score(task, requirement, resource)
    base["capability_match"] = capability["match"]
    base["capability_score"] = capability["score"]
    base["diagnostics"]["missing_capabilities"] = capability["missing"]
    base["diagnostics"]["missing_capacity"] = capability["missing_capacity"]
    if not capability["match"]:
        base["reason_codes"].append("capability_mismatch")
        return base

    route = _resource_route(task, resource, road_network)
    base.update(route)
    if not route["reachable"]:
        base["reason_codes"].extend(route["reason_codes"])
        return base

    base["status"] = "candidate"
    base["reason_codes"].append("capability_match")
    if resource.mobility_mode == "ground":
        base["reason_codes"].append("route_reachable")
    else:
        base["reason_codes"].append("direct_flight_estimate")
    return base


def _capability_score(task: ResourceTask, requirement: ResourceRequirement, resource: Resource) -> dict[str, Any]:
    required = _required_capabilities(task, requirement)
    missing = sorted(required - resource.capabilities)
    missing_capacity = []
    for name, minimum in requirement.minimum_capacity.items():
        if float(resource.capacity.get(name, 0.0)) < float(minimum):
            missing_capacity.append({"name": name, "required": minimum, "available": resource.capacity.get(name, 0.0)})
    if missing or missing_capacity:
        return {"match": False, "score": 0.0, "missing": missing, "missing_capacity": missing_capacity}
    if not required:
        return {"match": True, "score": round(max(0.0, min(1.0, resource.readiness)), 4), "missing": [], "missing_capacity": []}
    extra = len(resource.capabilities - required)
    score = 1.0 + min(extra, 3) * 0.03
    return {"match": True, "score": round(score, 4), "missing": [], "missing_capacity": []}


def _required_capabilities(task: ResourceTask, requirement: ResourceRequirement) -> frozenset[str]:
    return frozenset(set(task.required_capabilities) | set(requirement.required_capabilities))


def _resource_route(task: ResourceTask, resource: Resource, road_network: RoadNetwork) -> dict[str, Any]:
    if resource.mobility_mode == "ground":
        if not resource.location_node_id:
            return {
                "reachable": False,
                "route_status": "missing_origin_node",
                "reason_codes": ["missing_origin_node"],
            }
        try:
            result = calculate_route(
                RoutingRequest(
                    network=road_network,
                    start_node_id=resource.location_node_id,
                    destination_node_id=task.target_node_id,
                    algorithm="risk_aware_astar" if task.strategy == "safest_response" else "astar",
                    cost_mode="travel_time",
                    risk_weight=task.route_risk_weight if task.strategy == "safest_response" else 0.0,
                    blocked_edge_ids=task.blocked_edge_ids,
                    edge_status_overrides=task.edge_status_overrides,  # type: ignore[arg-type]
                    edge_risk_overrides=task.edge_risk_overrides,
                    vehicle_profile=resource.vehicle_profile,
                    metadata={"source": "resource_dispatch_route", "resource_id": resource.resource_id},
                )
            )
        except ValueError as exc:
            return {
                "reachable": False,
                "route_status": "route_error",
                "reason_codes": ["route_error"],
                "diagnostics": {"route_error": str(exc)},
            }
        return _route_result_payload(result)
    if resource.mobility_mode == "air":
        return _air_route_payload(task, resource, road_network)
    return {
        "reachable": False,
        "route_status": "unsupported_mobility",
        "reason_codes": ["unsupported_mobility"],
    }


def _route_result_payload(result: RouteResult) -> dict[str, Any]:
    payload = {
        "reachable": result.success,
        "route_status": result.status,
        "estimated_response_minutes": result.estimated_travel_time_minutes if result.success else None,
        "risk_score": result.risk_score if result.success else None,
        "distance_km": result.distance_km if result.success else None,
        "route": _route_summary(result),
        "terrain_metrics": dict(result.terrain_metrics),
        "road_metrics": dict(result.road_metrics),
        "accessibility": dict(result.accessibility),
        "reason_codes": [],
        "diagnostics": {"route_warnings": list(result.warnings)},
    }
    if not result.success:
        payload["reason_codes"].append("route_unreachable")
    if result.accessibility.get("inaccessible_edges_avoided"):
        payload["reason_codes"].append("vehicle_inaccessible")
    if result.blocked_edges_avoided:
        payload["reason_codes"].append("blocked_road")
    return payload


def _route_summary(result: RouteResult) -> dict[str, Any]:
    return {
        "route_id": f"{result.algorithm}_{result.metadata.get('cost_mode')}",
        "algorithm": result.algorithm,
        "cost_mode": result.metadata.get("cost_mode"),
        "status": result.status,
        "route_nodes": list(result.route_nodes),
        "route_edges": list(result.route_edges),
        "geometry": result.geometry,
        "distance_km": result.distance_km,
        "estimated_travel_time_minutes": result.estimated_travel_time_minutes,
        "risk_score": result.risk_score,
        "risk_cost": result.risk_cost,
        "terrain_metrics": dict(result.terrain_metrics),
        "road_metrics": dict(result.road_metrics),
        "accessibility": dict(result.accessibility),
        "blocked_edges_avoided": list(result.blocked_edges_avoided),
        "warnings": list(result.warnings),
    }


def _air_route_payload(task: ResourceTask, resource: Resource, road_network: RoadNetwork) -> dict[str, Any]:
    target = road_network.node(task.target_node_id)
    if resource.longitude is None or resource.latitude is None:
        return {
            "reachable": False,
            "route_status": "missing_air_origin",
            "reason_codes": ["missing_air_origin"],
        }
    speed = resource.response_speed_kmh or DEFAULT_AIR_SPEED_KMH
    distance = _haversine_km(resource.longitude, resource.latitude, target.longitude, target.latitude)
    eta = (distance / max(speed, 1.0)) * 60.0
    geometry = {"type": "LineString", "coordinates": [[resource.longitude, resource.latitude], [target.longitude, target.latitude]]}
    return {
        "reachable": True,
        "route_status": "ok",
        "estimated_response_minutes": round(eta, 3),
        "risk_score": float(resource.metadata.get("route_risk_score", 0.0)),
        "distance_km": round(distance, 4),
        "route": {
            "route_id": "direct_air_estimate",
            "algorithm": "direct_air_estimate",
            "cost_mode": "flight_time",
            "status": "ok",
            "route_nodes": [],
            "route_edges": [],
            "geometry": geometry,
            "distance_km": round(distance, 4),
            "estimated_travel_time_minutes": round(eta, 3),
            "risk_score": float(resource.metadata.get("route_risk_score", 0.0)),
            "risk_cost": 0.0,
            "terrain_metrics": {},
            "road_metrics": {},
            "accessibility": {"mobility_mode": "air", "model": "straight_line_flight_time"},
            "blocked_edges_avoided": [],
            "warnings": ["Air resource uses straight-line flight-time estimate, not road routing."],
        },
        "terrain_metrics": {},
        "road_metrics": {},
        "accessibility": {"mobility_mode": "air", "model": "straight_line_flight_time"},
        "reason_codes": [],
        "diagnostics": {"route_warnings": ["Air resource uses straight-line flight-time estimate, not road routing."]},
    }


def _score_candidates(strategy: DispatchStrategy, evaluations: list[dict[str, Any]]) -> None:
    reachable = [item for item in evaluations if item["status"] == "candidate"]
    max_eta = max((float(item["estimated_response_minutes"] or 0.0) for item in reachable), default=1.0) or 1.0
    for item in evaluations:
        if item["status"] != "candidate":
            item["score"] = 0.0
            continue
        eta_norm = float(item["estimated_response_minutes"] or 0.0) / max_eta
        risk = float(item["risk_score"] or 0.0)
        capability = float(item["capability_score"] or 0.0)
        readiness = float(item["resource"].get("readiness") or 0.0)
        if strategy == "fastest_response":
            score = capability * 45.0 + readiness * 20.0 + (1.0 - eta_norm) * 35.0 - risk * 8.0
        elif strategy == "safest_response":
            score = capability * 40.0 + readiness * 15.0 + (1.0 - risk) * 35.0 + (1.0 - eta_norm) * 10.0
        elif strategy == "capability_first":
            score = capability * 60.0 + readiness * 25.0 + (1.0 - eta_norm) * 10.0 + (1.0 - risk) * 5.0
        else:
            score = capability * 35.0 + readiness * 20.0 + (1.0 - eta_norm) * 25.0 + (1.0 - risk) * 20.0
        item["score"] = round(score, 4)
        item["diagnostics"]["score_components"] = {
            "strategy": strategy,
            "capability_score": capability,
            "readiness": readiness,
            "eta_norm": round(eta_norm, 4),
            "risk_score": risk,
        }
        item["reason_codes"].append(f"scored_by_{strategy}")


def _estimated_response(selected: list[dict[str, Any]]) -> dict[str, Any]:
    if not selected:
        return {
            "selected_count": 0,
            "max_eta_minutes": None,
            "average_eta_minutes": None,
            "max_route_risk_score": None,
            "average_route_risk_score": None,
        }
    etas = [float(item["estimated_response_minutes"] or 0.0) for item in selected]
    risks = [float(item["risk_score"] or 0.0) for item in selected]
    return {
        "selected_count": len(selected),
        "max_eta_minutes": round(max(etas), 3),
        "average_eta_minutes": round(sum(etas) / len(etas), 3),
        "max_route_risk_score": round(max(risks), 4),
        "average_route_risk_score": round(sum(risks) / len(risks), 4),
    }


def _warnings(shortages: list[dict[str, Any]], rejected: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    if shortages:
        warnings.append("Minimum resource requirements are not fully satisfied.")
    grouped: dict[str, int] = defaultdict(int)
    for item in rejected:
        for code in item.get("reason_codes", []):
            grouped[code] += 1
    for code in sorted(grouped):
        warnings.append(f"{grouped[code]} resource evaluation rejected: {code}.")
    return warnings


def _task_summary(task: ResourceTask, requirements: tuple[ResourceRequirement, ...]) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "task_type": task.task_type,
        "target_node_id": task.target_node_id,
        "priority": task.priority,
        "required_capabilities": sorted(task.required_capabilities),
        "minimum_resource_requirements": [_requirement_to_dict(requirement) for requirement in requirements],
        "desired_resource_requirements": [_requirement_to_dict(requirement) for requirement in task.desired_resource_requirements],
        "deadline_minutes": task.deadline_minutes,
        "metadata": dict(task.metadata),
    }


def _requirement_summary(task: ResourceTask, requirement: ResourceRequirement) -> dict[str, Any]:
    return {
        **_requirement_to_dict(requirement),
        "effective_required_capabilities": sorted(_required_capabilities(task, requirement)),
    }


def _requirement_to_dict(requirement: ResourceRequirement) -> dict[str, Any]:
    return {
        "resource_type": requirement.resource_type,
        "quantity": requirement.quantity,
        "required_capabilities": sorted(requirement.required_capabilities),
        "minimum_capacity": dict(requirement.minimum_capacity),
    }


def _origin(resource: Resource, road_network: RoadNetwork) -> dict[str, Any]:
    if resource.location_node_id:
        try:
            return road_network.node(resource.location_node_id).to_point()
        except ValueError:
            return {"node_id": resource.location_node_id, "longitude": resource.longitude, "latitude": resource.latitude}
    return {"node_id": None, "longitude": resource.longitude, "latitude": resource.latitude}


def _haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    radius_km = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    return 2 * radius_km * math.atan2(math.sqrt(a), math.sqrt(1 - a))