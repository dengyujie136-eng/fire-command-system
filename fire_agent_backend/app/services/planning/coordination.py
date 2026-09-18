"""Route-resource coordination service for emergency planning."""

from __future__ import annotations

from typing import Any, Mapping

from app.agents.resource_agent import ResourceAgent, ResourceAgentTask
from app.agents.route_agent import RouteAgent, RouteTask
from app.agents.schema import standardize_agent_result
from app.services.planning.models import PlanningResult, PlanningTask
from app.services.routing import VehicleProfile


def coordinate_route_resource_planning(
    task: PlanningTask,
    *,
    resource_agent: ResourceAgent | None = None,
    route_agent: RouteAgent | None = None,
) -> PlanningResult:
    """Coordinate resource dispatch and route explanation without new calculations."""
    resource_agent = resource_agent or ResourceAgent()
    route_agent = route_agent or RouteAgent()
    resource_task = task.to_resource_task()

    resource_agent_result = resource_agent.run(
        ResourceAgentTask(
            task=resource_task,
            resources=task.resource_inventory,
            road_network=task.road_network,
            mode=task.resource_strategy,
            task_id=task.task_id,
            incident_id=task.incident_id,
            metadata={
                **task.metadata,
                "coordination_layer": "planning_service",
            },
        )
    )
    resource_output = dict(resource_agent_result.get("output") or {})
    recommended_plan = resource_output.get("recommended_plan") or {}
    selected_resources = list(resource_output.get("selected_resources") or [])
    rejected_resources = list(resource_output.get("rejected_resources") or [])
    resource_shortage = list(resource_output.get("resource_shortage") or [])

    route_agent_results: dict[str, dict[str, Any]] = {}
    route_results: list[dict[str, Any]] = []
    operational_routes: list[dict[str, Any]] = []
    alternative_routes: list[dict[str, Any]] = []
    warnings = _warnings_from_resource(resource_output)
    diagnostics = {
        "coordination_service": "Route-Resource Planning Service",
        "resource_agent_status": resource_agent_result.get("status"),
        "route_agent_called_resource_ids": [],
        "uav_road_routing_called": False,
        "llm_used": False,
    }

    for resource in selected_resources:
        dispatch_route = dict(resource.get("route") or {})
        if _is_ground_resource(resource):
            route_result = route_agent.run(_route_task_for_resource(task, resource))
            route_agent_results[str(resource.get("resource_id"))] = route_result
            route_output = dict(route_result.get("output") or {})
            route_results.append(
                {
                    "resource_id": resource.get("resource_id"),
                    "route_agent_result": route_result,
                    "route_summary": route_output.get("route_summary"),
                    "candidate_routes": route_output.get("candidate_routes", []),
                    "recommended_route": route_output.get("recommended_route"),
                }
            )
            diagnostics["route_agent_called_resource_ids"].append(resource.get("resource_id"))
            alternative_routes.extend(_alternative_routes_for_resource(resource, route_output, dispatch_route))
            chosen_route = _choose_operational_route(task, dispatch_route, route_output)
        else:
            chosen_route = dispatch_route

        operational_routes.append(_operational_route(task, resource, dispatch_route, chosen_route, recommended_plan))

    consistency = _consistency(operational_routes)
    diagnostics["consistency"] = consistency
    diagnostics["resource_route_conflicts"] = [item for item in consistency if item.get("status") != "consistent"]

    if not selected_resources and not warnings:
        warnings.append("No selected resources were available for route-resource coordination.")

    status = _planning_status(resource_agent_result, resource_shortage, selected_resources)
    return PlanningResult(
        success=status == "success",
        status=status,
        task=_task_summary(task),
        resource_result=resource_output,
        route_results=route_results,
        route_agent_results=route_agent_results,
        resource_agent_result=resource_agent_result,
        selected_resources=selected_resources,
        operational_routes=operational_routes,
        alternative_routes=alternative_routes,
        rejected_resources=rejected_resources,
        resource_shortage=resource_shortage,
        estimated_response=dict(recommended_plan.get("estimated_response") or resource_output.get("resource_summary") or {}),
        warnings=warnings,
        diagnostics=diagnostics,
        metadata={
            "planning_unit": "Route-Resource Planning Service",
            "resource_agent_used": True,
            "route_agent_used_for_ground_selected_resources": bool(route_agent_results),
            "resource_calculation_unit_used": True,
            "routing_unit_used": True,
            "llm_used": False,
            "standard_outputs": _standard_outputs(resource_agent_result, route_agent_results),
        },
    )


def _route_task_for_resource(task: PlanningTask, resource: Mapping[str, Any]) -> RouteTask:
    origin = dict(resource.get("origin") or {})
    start_node_id = origin.get("node_id") or resource.get("location_node_id")
    if not start_node_id:
        raise ValueError(f"Selected ground resource {resource.get('resource_id')} has no origin node.")
    return RouteTask(
        road_network=task.road_network,
        start_node_id=str(start_node_id),
        destination_node_id=task.target_node_id,
        objective=task.route_objective,
        vehicle=_vehicle_for_resource(resource),
        risk_weight=task.route_risk_weight,
        blocked_edge_ids=task.blocked_edge_ids,
        edge_status_overrides=task.edge_status_overrides,
        edge_risk_overrides=task.edge_risk_overrides,
        task_id=task.task_id,
        incident_id=task.incident_id,
        purpose="route_resource_coordination_alternatives",
        metadata={
            **task.metadata,
            "resource_id": resource.get("resource_id"),
            "source": "route_resource_planning",
        },
    )


def _vehicle_for_resource(resource: Mapping[str, Any]) -> str | VehicleProfile:
    resource_type = resource.get("resource_type")
    if resource_type == "fire_team":
        return "light_utility_vehicle"
    return "fire_engine"


def _is_ground_resource(resource: Mapping[str, Any]) -> bool:
    summary = dict(resource.get("resource") or {})
    return summary.get("mobility_mode", "ground") == "ground"


def _alternative_routes_for_resource(
    resource: Mapping[str, Any],
    route_output: Mapping[str, Any],
    dispatch_route: Mapping[str, Any],
) -> list[dict[str, Any]]:
    by_path: dict[tuple[Any, ...], dict[str, Any]] = {}
    for candidate in route_output.get("candidate_routes") or []:
        if not candidate.get("success"):
            continue
        key = _route_identity(candidate)
        entry = by_path.setdefault(
            key,
            {
                "resource_id": resource.get("resource_id"),
                "resource_type": resource.get("resource_type"),
                "route_role": "alternative_route",
                "objectives": [],
                "route": candidate,
                "matches_operational_dispatch_route": _same_route(candidate, dispatch_route),
                "source": "RouteAgent",
            },
        )
        entry["objectives"].append(candidate.get("objective"))
    return list(by_path.values())


def _route_identity(route: Mapping[str, Any]) -> tuple[Any, ...]:
    edges = tuple(route.get("route_edges") or [])
    if edges:
        return ("edges", edges)
    geometry = route.get("geometry") or {}
    coordinates = tuple(tuple(point) for point in geometry.get("coordinates", []))
    return ("geometry", coordinates)


def _same_route(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    if not left or not right:
        return False
    return _route_identity(left) == _route_identity(right)


def _choose_operational_route(
    task: PlanningTask,
    dispatch_route: Mapping[str, Any],
    route_output: Mapping[str, Any],
) -> dict[str, Any]:
    if task.operational_route_source == "route_preference":
        recommended = route_output.get("recommended_route")
        if recommended:
            return dict(recommended)
    return dict(dispatch_route)


def _operational_route(
    task: PlanningTask,
    resource: Mapping[str, Any],
    dispatch_route: Mapping[str, Any],
    chosen_route: Mapping[str, Any],
    recommended_plan: Mapping[str, Any],
) -> dict[str, Any]:
    route_source = "resource_dispatch_result"
    consistency_status = "consistent"
    reason = "Operational route uses the ResourceDispatchResult route that was used for ETA and risk evaluation."
    if not _same_route(chosen_route, dispatch_route):
        route_source = "route_agent_route_preference"
        consistency_status = "role_differentiated"
        reason = "Resource selection used dispatch_route; operational route uses explicit route preference, so roles are separated."
    if dict(chosen_route).get("algorithm") == "direct_air_estimate":
        route_source = "resource_direct_air_estimate"
        reason = "Air resource uses Resource Calculation Unit simplified direct flight-time estimate, not road routing."
    return {
        "resource_id": resource.get("resource_id"),
        "resource_type": resource.get("resource_type"),
        "resource_name": resource.get("name"),
        "origin": dict(resource.get("origin") or {}),
        "target": dict(resource.get("target") or {}),
        "route_role": "operational_route",
        "route_source": route_source,
        "source_plan_id": recommended_plan.get("plan_id"),
        "source_strategy": recommended_plan.get("strategy"),
        "route": dict(chosen_route),
        "eta_minutes": chosen_route.get("estimated_travel_time_minutes"),
        "risk_score": chosen_route.get("risk_score"),
        "distance_km": chosen_route.get("distance_km"),
        "geometry": chosen_route.get("geometry"),
        "terrain_metrics": dict(chosen_route.get("terrain_metrics") or {}),
        "road_metrics": dict(chosen_route.get("road_metrics") or {}),
        "accessibility": dict(chosen_route.get("accessibility") or {}),
        "consistency": {
            "status": consistency_status,
            "matches_resource_dispatch_route": _same_route(chosen_route, dispatch_route),
            "eta_matches_resource": chosen_route.get("estimated_travel_time_minutes") == dispatch_route.get("estimated_travel_time_minutes"),
            "risk_matches_resource": chosen_route.get("risk_score") == dispatch_route.get("risk_score"),
            "geometry_matches_resource": chosen_route.get("geometry") == dispatch_route.get("geometry"),
            "reason": reason,
        },
    }


def _consistency(operational_routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "resource_id": route.get("resource_id"),
            "status": route.get("consistency", {}).get("status"),
            "eta_matches_resource": route.get("consistency", {}).get("eta_matches_resource"),
            "risk_matches_resource": route.get("consistency", {}).get("risk_matches_resource"),
            "geometry_matches_resource": route.get("consistency", {}).get("geometry_matches_resource"),
            "reason": route.get("consistency", {}).get("reason"),
        }
        for route in operational_routes
    ]


def _warnings_from_resource(resource_output: Mapping[str, Any]) -> list[str]:
    warnings = []
    seen: set[str] = set()
    for warning in resource_output.get("warnings") or []:
        if warning not in seen:
            warnings.append(warning)
            seen.add(warning)
    return warnings


def _planning_status(resource_agent_result: Mapping[str, Any], shortages: list[dict[str, Any]], selected: list[dict[str, Any]]) -> str:
    if resource_agent_result.get("status") != "success":
        return "error"
    if shortages:
        return "partial"
    if not selected:
        return "failed"
    return "success"


def _task_summary(task: PlanningTask) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "incident_id": task.incident_id,
        "task_type": task.task_type,
        "target_node_id": task.target_node_id,
        "priority": task.priority,
        "protection_target": task.protection_target,
        "deadline_minutes": task.deadline_minutes,
        "scenario_version": task.scenario_version,
        "resource_strategy": task.resource_strategy,
        "route_objective": task.route_objective,
        "operational_route_source": task.operational_route_source,
        "blocked_edge_ids": sorted(task.blocked_edge_ids),
        "edge_status_overrides": dict(task.edge_status_overrides),
        "edge_risk_overrides": dict(task.edge_risk_overrides),
        "metadata": dict(task.metadata),
    }


def _standard_outputs(
    resource_agent_result: Mapping[str, Any],
    route_agent_results: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "resource": standardize_agent_result(resource_agent_result),
        "routes": {
            resource_id: standardize_agent_result(route_result)
            for resource_id, route_result in route_agent_results.items()
        },
    }
