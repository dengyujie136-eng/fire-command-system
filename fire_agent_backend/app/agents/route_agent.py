"""Independent route planning agent backed by the routing calculation unit."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal, Mapping

from app.agents.base import AgentResult, BaseAgent, agent_result
from app.services.routing import (
    RoadNetwork,
    RouteResult,
    RoutingRequest,
    VehicleProfile,
    calculate_route,
    default_fire_engine_profile,
    light_utility_vehicle_profile,
)

RouteObjective = Literal["shortest", "fastest", "safest", "compare"]


@dataclass(frozen=True)
class RouteTask:
    road_network: RoadNetwork
    start_node_id: str
    destination_node_id: str
    objective: RouteObjective = "compare"
    vehicle: str | VehicleProfile = "fire_engine"
    risk_weight: float = 20.0
    blocked_edge_ids: frozenset[str] = field(default_factory=frozenset)
    avoid_edge_ids: frozenset[str] = field(default_factory=frozenset)
    edge_status_overrides: dict[str, str] = field(default_factory=dict)
    edge_risk_overrides: dict[str, float] = field(default_factory=dict)
    task_id: str | None = None
    incident_id: str | None = None
    target_name: str | None = None
    purpose: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class RouteAgent(BaseAgent):
    """Uses route algorithms and turns their results into AgentResult output."""

    agent_name = "RouteAgent"

    def run(
        self,
        context: RouteTask | RoutingRequest,
        prior_results: Mapping[str, AgentResult] | None = None,
    ) -> AgentResult:
        try:
            task = _coerce_task(context)
            _validate_objective(task.objective)
            vehicle_profile = _resolve_vehicle_profile(task.vehicle)
            candidate_objectives = _candidate_objectives(task.objective)
            candidates = [
                _candidate_route(
                    objective,
                    calculate_route(_request_for_objective(task, objective, vehicle_profile)),
                )
                for objective in candidate_objectives
            ]
            recommended_route = _recommend_route(task.objective, candidates)
            route_comparison = _route_comparison(candidates)
            warnings = _warnings(candidates)
            route_summary = _route_summary(task, candidates, recommended_route)
            analysis = _analysis(task, candidates, recommended_route, warnings)
            visualization = _visualization_layers(candidates, recommended_route)
            decision = _decision(task, candidates, recommended_route)
            provenance = _provenance(task, vehicle_profile, candidates)
            algorithm = _algorithm_output(task, vehicle_profile, candidates, route_comparison)

            output = {
                "route_summary": route_summary,
                "candidate_routes": candidates,
                "recommended_route": recommended_route,
                "route_comparison": route_comparison,
                "warnings": warnings,
                "algorithm": algorithm,
                "analysis": analysis,
                "visualization": visualization,
                "decision": decision,
                "provenance": provenance,
            }
            return agent_result(
                self.agent_name,
                output=output,
                reasoning=_reasoning(task, candidates, recommended_route, warnings),
            )
        except ValueError as exc:
            message = str(exc)
            output = {
                "route_summary": {"status": "error", "reachable": False, "error": message},
                "candidate_routes": [],
                "recommended_route": None,
                "route_comparison": {},
                "warnings": [message],
                "algorithm": {"result": {}, "metrics": {}, "artifacts": []},
                "analysis": {"summary": message, "reasoning": [], "factors": [], "warnings": [message], "confidence": None},
                "visualization": {"layers": [], "timeline": [], "annotations": [], "interactions": []},
                "decision": {"recommendations": [], "priority": None, "actions": [], "constraints": [], "basis": []},
                "provenance": {"source_agent": self.agent_name, "data_sources": [], "provider": None, "model": None},
            }
            return agent_result(
                self.agent_name,
                status="error",
                output=output,
                reasoning=["RouteAgent rejected invalid route task input before route calculation."],
            )


def _coerce_task(context: RouteTask | RoutingRequest) -> RouteTask:
    if isinstance(context, RouteTask):
        return context
    if isinstance(context, RoutingRequest):
        objective = str(context.metadata.get("objective") or _objective_from_request(context))
        return RouteTask(
            road_network=context.network,
            start_node_id=context.start_node_id,
            destination_node_id=context.destination_node_id,
            objective=objective,  # type: ignore[arg-type]
            vehicle=context.vehicle_profile or "fire_engine",
            risk_weight=context.risk_weight,
            blocked_edge_ids=context.blocked_edge_ids,
            edge_status_overrides=dict(context.edge_status_overrides),
            edge_risk_overrides=dict(context.edge_risk_overrides),
            task_id=context.metadata.get("task_id"),
            incident_id=context.metadata.get("incident_id"),
            target_name=context.metadata.get("target_name"),
            purpose=context.metadata.get("purpose"),
            metadata=dict(context.metadata),
        )
    raise ValueError("RouteAgent requires RouteTask or RoutingRequest input.")


def _objective_from_request(request: RoutingRequest) -> str:
    if request.algorithm == "risk_aware_astar":
        return "safest"
    if request.cost_mode == "travel_time":
        return "fastest"
    return "shortest"


def _validate_objective(objective: str) -> None:
    if objective not in {"shortest", "fastest", "safest", "compare"}:
        raise ValueError(f"Unsupported route objective: {objective}")


def _resolve_vehicle_profile(vehicle: str | VehicleProfile) -> VehicleProfile:
    if isinstance(vehicle, VehicleProfile):
        return vehicle
    if vehicle == "fire_engine":
        return default_fire_engine_profile()
    if vehicle == "light_utility_vehicle":
        return light_utility_vehicle_profile()
    raise ValueError(f"Unsupported vehicle profile: {vehicle}")


def _candidate_objectives(objective: str) -> list[str]:
    if objective == "compare":
        return ["shortest", "fastest", "safest"]
    return [objective]


def _request_for_objective(task: RouteTask, objective: str, vehicle_profile: VehicleProfile) -> RoutingRequest:
    if objective == "shortest":
        algorithm = "astar"
        cost_mode = "distance"
        risk_weight = 0.0
    elif objective == "fastest":
        algorithm = "astar"
        cost_mode = "travel_time"
        risk_weight = 0.0
    elif objective == "safest":
        algorithm = "risk_aware_astar"
        cost_mode = "travel_time"
        risk_weight = task.risk_weight
    else:
        raise ValueError(f"Unsupported route objective: {objective}")

    return RoutingRequest(
        network=task.road_network,
        start_node_id=task.start_node_id,
        destination_node_id=task.destination_node_id,
        algorithm=algorithm,  # type: ignore[arg-type]
        cost_mode=cost_mode,  # type: ignore[arg-type]
        risk_weight=risk_weight,
        blocked_edge_ids=frozenset(set(task.blocked_edge_ids) | set(task.avoid_edge_ids)),
        edge_status_overrides=task.edge_status_overrides,  # type: ignore[arg-type]
        edge_risk_overrides=task.edge_risk_overrides,
        vehicle_profile=vehicle_profile,
        metadata={
            **task.metadata,
            "objective": objective,
            "task_id": task.task_id,
            "incident_id": task.incident_id,
            "target_name": task.target_name,
            "purpose": task.purpose,
        },
    )


def _candidate_route(objective: str, result: RouteResult) -> dict[str, Any]:
    cost_mode = result.metadata.get("cost_mode")
    route_id = f"{objective}_{result.algorithm}_{cost_mode}"
    return {
        "route_id": route_id,
        "objective": objective,
        "status": result.status,
        "success": result.success,
        "algorithm": result.algorithm,
        "cost_mode": cost_mode,
        "start": result.start,
        "destination": result.destination,
        "route_nodes": list(result.route_nodes),
        "route_edges": list(result.route_edges),
        "geometry": result.geometry,
        "distance_km": result.distance_km,
        "estimated_travel_time_minutes": result.estimated_travel_time_minutes,
        "risk_score": result.risk_score,
        "risk_cost": result.risk_cost,
        "total_cost": result.total_cost,
        "terrain_metrics": dict(result.terrain_metrics),
        "road_metrics": dict(result.road_metrics),
        "accessibility": dict(result.accessibility),
        "blocked_edges_avoided": list(result.blocked_edges_avoided),
        "warnings": list(result.warnings),
        "metadata": dict(result.metadata),
    }


def _recommend_route(objective: str, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    reachable = [candidate for candidate in candidates if candidate.get("success")]
    if not reachable:
        return None
    if objective != "compare":
        return reachable[0]
    max_eta = max(float(candidate["estimated_travel_time_minutes"] or 0.0) for candidate in reachable) or 1.0
    max_distance = max(float(candidate["distance_km"] or 0.0) for candidate in reachable) or 1.0

    def score(candidate: dict[str, Any]) -> float:
        eta = float(candidate["estimated_travel_time_minutes"] or 0.0) / max_eta
        distance = float(candidate["distance_km"] or 0.0) / max_distance
        risk = float(candidate["risk_score"] or 0.0)
        inaccessible = len(candidate.get("accessibility", {}).get("inaccessible_edges_avoided", []))
        return eta + (risk * 2.0) + (distance * 0.15) + (inaccessible * 0.05)

    return min(reachable, key=score)


def _route_summary(task: RouteTask, candidates: list[dict[str, Any]], recommended_route: dict[str, Any] | None) -> dict[str, Any]:
    reachable = [candidate for candidate in candidates if candidate.get("success")]
    return {
        "status": "completed" if candidates else "error",
        "objective": task.objective,
        "start_node_id": task.start_node_id,
        "destination_node_id": task.destination_node_id,
        "vehicle": _vehicle_label(task.vehicle),
        "reachable": bool(reachable),
        "candidate_count": len(candidates),
        "reachable_candidate_count": len(reachable),
        "recommended_route_id": recommended_route.get("route_id") if recommended_route else None,
        "task_id": task.task_id,
        "incident_id": task.incident_id,
        "target_name": task.target_name,
        "purpose": task.purpose,
    }


def _route_comparison(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        candidate["objective"]: {
            "route_id": candidate["route_id"],
            "success": candidate["success"],
            "distance_km": candidate["distance_km"],
            "estimated_travel_time_minutes": candidate["estimated_travel_time_minutes"],
            "risk_score": candidate["risk_score"],
            "total_cost": candidate["total_cost"],
            "max_slope_percent": candidate.get("terrain_metrics", {}).get("max_slope_percent"),
            "unpaved_distance_km": candidate.get("road_metrics", {}).get("unpaved_distance_km"),
            "forest_road_distance_km": candidate.get("road_metrics", {}).get("forest_road_distance_km"),
            "inaccessible_edges_avoided": candidate.get("accessibility", {}).get("inaccessible_edges_avoided", []),
            "warnings": candidate.get("warnings", []),
        }
        for candidate in candidates
    }


def _warnings(candidates: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    seen: set[str] = set()
    if candidates and not any(candidate.get("success") for candidate in candidates):
        warnings.append("No reachable route candidate was found.")
        seen.add(warnings[-1])
    for candidate in candidates:
        for warning in candidate.get("warnings", []):
            if warning not in seen:
                warnings.append(warning)
                seen.add(warning)
    return warnings


def _analysis(
    task: RouteTask,
    candidates: list[dict[str, Any]],
    recommended_route: dict[str, Any] | None,
    warnings: list[str],
) -> dict[str, Any]:
    factors = ["distance", "terrain-aware ETA", "edge fire risk", "road condition", "vehicle accessibility"]
    if not recommended_route:
        summary = "No reachable route was found for the supplied start, destination, road network, and vehicle constraints."
    elif task.objective == "compare":
        summary = f"Compared {len(candidates)} route candidates and selected {recommended_route['objective']} by deterministic ETA, risk, and accessibility scoring."
    else:
        summary = f"Selected the {recommended_route['objective']} route from the Route Calculation Unit result."
    key_factors = _key_factors(candidates, recommended_route)
    return {
        "summary": summary,
        "comparison": _route_comparison(candidates),
        "key_factors": key_factors,
        "reasoning": key_factors,
        "factors": factors,
        "warnings": warnings,
        "confidence": None,
    }


def _key_factors(candidates: list[dict[str, Any]], recommended_route: dict[str, Any] | None) -> list[str]:
    factors: list[str] = []
    by_objective = {candidate["objective"]: candidate for candidate in candidates if candidate.get("success")}
    shortest = by_objective.get("shortest")
    fastest = by_objective.get("fastest")
    safest = by_objective.get("safest")
    if shortest and fastest and shortest["route_id"] != fastest["route_id"]:
        factors.append("Shortest route has the lowest distance, while fastest route has the lowest terrain-aware ETA.")
    if fastest and safest and fastest["route_id"] != safest["route_id"]:
        factors.append("Safest route lowers fire-risk exposure at the cost of different travel metrics.")
    if recommended_route:
        factors.append(f"Recommended route comes directly from calculated candidate {recommended_route['route_id']}.")
    for candidate in candidates:
        if candidate.get("accessibility", {}).get("inaccessible_edges_avoided"):
            factors.append("Vehicle-inaccessible road segments were excluded before route selection.")
            break
    return factors


def _visualization_layers(
    candidates: list[dict[str, Any]],
    recommended_route: dict[str, Any] | None,
) -> dict[str, Any]:
    recommended_id = recommended_route.get("route_id") if recommended_route else None
    layers = []
    for candidate in candidates:
        if not candidate.get("success"):
            continue
        layers.append(
            {
                "id": candidate["route_id"],
                "type": "route",
                "layer_type": "route",
                "route_role": candidate["objective"],
                "is_recommended": candidate["route_id"] == recommended_id,
                "geometry": candidate["geometry"],
                "properties": {
                    "route_nodes": candidate["route_nodes"],
                    "route_edges": candidate["route_edges"],
                    "distance_km": candidate["distance_km"],
                    "estimated_travel_time_minutes": candidate["estimated_travel_time_minutes"],
                    "risk_score": candidate["risk_score"],
                    "terrain_metrics": candidate["terrain_metrics"],
                    "road_metrics": candidate["road_metrics"],
                    "accessibility": candidate["accessibility"],
                },
            }
        )
    return {
        "layers": layers,
        "timeline": [],
        "annotations": [],
        "interactions": [{"type": "inspect_route", "target": layer["id"]} for layer in layers],
    }


def _decision(
    task: RouteTask,
    candidates: list[dict[str, Any]],
    recommended_route: dict[str, Any] | None,
) -> dict[str, Any]:
    constraints = []
    if task.blocked_edge_ids:
        constraints.append({"type": "blocked_edges", "edge_ids": sorted(task.blocked_edge_ids)})
    if task.avoid_edge_ids:
        constraints.append({"type": "avoid_edges", "edge_ids": sorted(task.avoid_edge_ids)})
    if task.edge_status_overrides:
        constraints.append({"type": "edge_status_overrides", "values": dict(task.edge_status_overrides)})
    return {
        "recommended_route": recommended_route,
        "recommendation_reason": _recommendation_reason(task.objective, recommended_route),
        "alternatives": [candidate for candidate in candidates if candidate is not recommended_route],
        "constraints": constraints,
        "recommendations": [recommended_route] if recommended_route else [],
        "priority": None,
        "actions": [],
        "basis": ["Route Calculation Unit result", "deterministic objective mapping"],
    }


def _recommendation_reason(objective: str, recommended_route: dict[str, Any] | None) -> str:
    if not recommended_route:
        return "No recommendation is available because no route candidate is reachable."
    if objective == "shortest":
        return "Shortest objective selects the calculated distance-minimizing route."
    if objective == "fastest":
        return "Fastest objective selects the calculated terrain-aware ETA-minimizing route."
    if objective == "safest":
        return "Safest objective selects the calculated risk-aware route where edge fire risk participates in search cost."
    return "Compare objective selects a calculated candidate using deterministic ETA, risk, distance, and accessibility scoring."


def _provenance(task: RouteTask, vehicle_profile: VehicleProfile, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    network_source = task.metadata.get("source") or task.metadata.get("network_source") or "road_network"
    algorithms = sorted({candidate["algorithm"] for candidate in candidates})
    return {
        "source_agent": "RouteAgent",
        "data_sources": [
            "RouteTask",
            "Route Calculation Unit",
            str(network_source),
            "edge risk scores or request risk overrides",
        ],
        "provider": None,
        "model": None,
        "routing_algorithms": algorithms,
        "vehicle_profile": vehicle_profile.vehicle_type,
        "network_source": network_source,
        "risk_data_source": task.metadata.get("risk_data_source", "edge_risk_score/request_overrides"),
        "synthetic": bool(task.metadata.get("synthetic") or "synthetic" in str(network_source).lower()),
    }


def _algorithm_output(
    task: RouteTask,
    vehicle_profile: VehicleProfile,
    candidates: list[dict[str, Any]],
    route_comparison: dict[str, Any],
) -> dict[str, Any]:
    return {
        "result": {
            "objective": task.objective,
            "candidate_routes": candidates,
            "route_comparison": route_comparison,
        },
        "metrics": {
            "candidate_count": len(candidates),
            "reachable_candidate_count": sum(1 for candidate in candidates if candidate.get("success")),
            "vehicle_type": vehicle_profile.vehicle_type,
            "risk_weight": task.risk_weight,
        },
        "artifacts": [],
    }


def _reasoning(
    task: RouteTask,
    candidates: list[dict[str, Any]],
    recommended_route: dict[str, Any] | None,
    warnings: list[str],
) -> list[str]:
    reasoning = [
        "RouteAgent called the public Route Calculation Unit entry point for each requested route objective.",
        "No LLM call was used; recommendation is deterministic and based only on calculated RouteResult fields.",
    ]
    if task.objective == "compare":
        reasoning.append("Computed shortest, fastest, and safest candidates for objective comparison.")
    if recommended_route:
        reasoning.append(f"Recommended route {recommended_route['route_id']} is one of the calculated candidate routes.")
    reasoning.extend(warnings)
    return reasoning


def _vehicle_label(vehicle: str | VehicleProfile) -> str:
    if isinstance(vehicle, VehicleProfile):
        return vehicle.vehicle_type
    return vehicle