"""Independent resource dispatch agent backed by the calculation unit."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal, Mapping, Sequence

from app.agents.base import AgentResult, BaseAgent, agent_result
from app.services.resources import Resource, ResourceDispatchResult, ResourceTask, calculate_resource_dispatch
from app.services.resources.models import DispatchStrategy
from app.services.routing import RoadNetwork

ResourceAgentMode = Literal["fastest_response", "safest_response", "capability_first", "balanced", "compare"]

DISPATCH_STRATEGIES: tuple[DispatchStrategy, ...] = (
    "fastest_response",
    "safest_response",
    "capability_first",
    "balanced",
)
COMPARE_STRATEGIES: tuple[DispatchStrategy, ...] = DISPATCH_STRATEGIES


@dataclass(frozen=True)
class ResourceAgentTask:
    """Input envelope for ResourceAgent."""

    task: ResourceTask
    resources: Sequence[Resource]
    road_network: RoadNetwork
    mode: ResourceAgentMode = "balanced"
    compare_strategies: tuple[DispatchStrategy, ...] = COMPARE_STRATEGIES
    task_id: str | None = None
    incident_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ResourceAgent(BaseAgent):
    """Turns calculated resource dispatch results into AgentResult output."""

    agent_name = "ResourceAgent"

    def run(
        self,
        context: ResourceAgentTask,
        prior_results: Mapping[str, AgentResult] | None = None,
    ) -> AgentResult:
        try:
            task = _coerce_task(context)
            _validate_mode(task.mode)
            _validate_compare_strategies(task.compare_strategies)

            plans = _dispatch_plans(task)
            recommended_plan = _recommend_plan(task.mode, plans)
            warnings = _warnings(task, plans)
            resource_summary = _resource_summary(task, plans, recommended_plan)
            comparison = _dispatch_comparison(plans)
            output = {
                "resource_summary": resource_summary,
                "dispatch_plans": plans,
                "recommended_plan": recommended_plan,
                "selected_resources": recommended_plan.get("selected_resources", []) if recommended_plan else [],
                "candidate_resources": recommended_plan.get("candidate_resources", []) if recommended_plan else [],
                "rejected_resources": recommended_plan.get("rejected_resources", []) if recommended_plan else [],
                "resource_shortage": recommended_plan.get("resource_shortage", []) if recommended_plan else [],
                "dispatch_comparison": comparison,
                "warnings": warnings,
            }
            output["algorithm"] = _algorithm_output(task, plans, comparison)
            output["analysis"] = _analysis(task, plans, recommended_plan, warnings)
            output["visualization"] = _visualization(task, recommended_plan)
            output["decision"] = _decision(task, plans, recommended_plan)
            output["provenance"] = _provenance(task, plans)
            return agent_result(self.agent_name, output=output, reasoning=_reasoning(task, plans, recommended_plan, warnings))
        except ValueError as exc:
            message = str(exc)
            output = {
                "resource_summary": {"status": "error", "error": message},
                "dispatch_plans": [],
                "recommended_plan": None,
                "selected_resources": [],
                "candidate_resources": [],
                "rejected_resources": [],
                "resource_shortage": [],
                "dispatch_comparison": {},
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
                reasoning=["ResourceAgent rejected invalid resource task input before dispatch calculation."],
            )


def _coerce_task(context: ResourceAgentTask) -> ResourceAgentTask:
    if isinstance(context, ResourceAgentTask):
        return context
    raise ValueError("ResourceAgent requires ResourceAgentTask input.")


def _validate_mode(mode: str) -> None:
    if mode not in {*DISPATCH_STRATEGIES, "compare"}:
        raise ValueError(f"Unsupported resource dispatch mode: {mode}")


def _validate_compare_strategies(strategies: Sequence[str]) -> None:
    invalid = [strategy for strategy in strategies if strategy not in DISPATCH_STRATEGIES]
    if invalid:
        raise ValueError(f"Unsupported compare dispatch strategy: {invalid[0]}")


def _dispatch_plans(task: ResourceAgentTask) -> list[dict[str, Any]]:
    strategies = task.compare_strategies if task.mode == "compare" else (task.mode,)
    return [
        _dispatch_plan(
            strategy=strategy,
            result=calculate_resource_dispatch(
                replace(task.task, strategy=strategy),
                list(task.resources),
                task.road_network,
            ),
        )
        for strategy in strategies
    ]


def _dispatch_plan(strategy: str, result: ResourceDispatchResult) -> dict[str, Any]:
    payload = result.to_dict()
    return {
        "plan_id": f"resource_plan_{strategy}",
        "strategy": payload["strategy"],
        "success": payload["success"],
        "status": payload["status"],
        "task": payload["task"],
        "selected_resources": payload["selected_resources"],
        "candidate_resources": payload["candidate_resources"],
        "rejected_resources": payload["rejected_resources"],
        "resource_shortage": payload["resource_shortage"],
        "total_resource_count": payload["total_resource_count"],
        "estimated_response": payload["estimated_response"],
        "warnings": payload["warnings"],
        "metadata": payload["metadata"],
        "summary_metrics": _summary_metrics(payload),
        "rejection_explanations": _rejection_explanations(payload["rejected_resources"]),
    }


def _summary_metrics(plan: Mapping[str, Any]) -> dict[str, Any]:
    selected = list(plan.get("selected_resources") or [])
    shortages = list(plan.get("resource_shortage") or [])
    return {
        "selected_count": len(selected),
        "candidate_count": len(plan.get("candidate_resources") or []),
        "rejected_count": len(plan.get("rejected_resources") or []),
        "shortage_count": len(shortages),
        "shortage_total": sum(int(item.get("shortage") or 0) for item in shortages),
        "max_eta_minutes": _max_metric(selected, "estimated_response_minutes"),
        "max_risk_score": _max_metric(selected, "risk_score"),
        "route_count": sum(1 for item in selected if item.get("route")),
    }


def _max_metric(items: Sequence[Mapping[str, Any]], key: str) -> float | None:
    values = [float(item[key]) for item in items if item.get(key) is not None]
    return max(values) if values else None


def _rejection_explanations(rejected_resources: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "resource_id": item.get("resource_id"),
            "resource_type": item.get("resource_type"),
            "reason_codes": list(item.get("reason_codes") or []),
            "summary": _rejection_summary(item),
            "diagnostics": dict(item.get("diagnostics") or {}),
        }
        for item in rejected_resources
    ]


def _rejection_summary(item: Mapping[str, Any]) -> str:
    resource_id = item.get("resource_id")
    codes = set(item.get("reason_codes") or [])
    if "unavailable" in codes:
        return f"{resource_id} was rejected because it is not available."
    if "capability_mismatch" in codes:
        return f"{resource_id} was rejected because required capabilities or capacity were missing."
    if "route_unreachable" in codes:
        return f"{resource_id} was rejected because no reachable route to the target was found."
    if "resource_type_not_required" in codes:
        return f"{resource_id} was rejected because its type was not requested for this task."
    return f"{resource_id} was rejected by the Resource Calculation Unit."


def _recommend_plan(mode: str, plans: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not plans:
        return None
    if mode != "compare":
        return plans[0]
    if not any(plan.get("selected_resources") for plan in plans):
        return None

    max_eta = max((_metric_or_default(plan, "max_eta_minutes", 0.0) for plan in plans), default=0.0) or 1.0
    preference = {"balanced": 0.3, "safest_response": 0.2, "fastest_response": 0.1, "capability_first": 0.0}

    def score(plan: Mapping[str, Any]) -> float:
        metrics = dict(plan.get("summary_metrics") or {})
        shortage_penalty = float(metrics.get("shortage_total") or 0) * 100.0
        eta_penalty = (_metric_or_default(plan, "max_eta_minutes", max_eta) / max_eta) * 25.0
        risk_penalty = _metric_or_default(plan, "max_risk_score", 1.0) * 25.0
        selected_bonus = float(metrics.get("selected_count") or 0) * 5.0
        success_bonus = 100.0 if plan.get("success") else 0.0
        return success_bonus + selected_bonus - shortage_penalty - eta_penalty - risk_penalty + preference.get(str(plan.get("strategy")), 0.0)

    best = max(plans, key=lambda plan: (score(plan), -_strategy_order(str(plan.get("strategy")))))
    best["recommendation_score"] = round(score(best), 6)
    return best


def _metric_or_default(plan: Mapping[str, Any], key: str, default: float) -> float:
    value = dict(plan.get("summary_metrics") or {}).get(key)
    if value is None:
        return default
    return float(value)


def _strategy_order(strategy: str) -> int:
    try:
        return list(COMPARE_STRATEGIES).index(strategy) + 1
    except ValueError:
        return 99


def _resource_summary(
    task: ResourceAgentTask,
    plans: list[dict[str, Any]],
    recommended_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    recommended_metrics = dict(recommended_plan.get("summary_metrics") or {}) if recommended_plan else {}
    return {
        "status": "completed" if plans else "error",
        "mode": task.mode,
        "task_id": task.task_id or task.task.task_id,
        "incident_id": task.incident_id,
        "task_type": task.task.task_type,
        "target_node_id": task.task.target_node_id,
        "inventory_count": len(task.resources),
        "plan_count": len(plans),
        "recommended_plan_id": recommended_plan.get("plan_id") if recommended_plan else None,
        "recommended_strategy": recommended_plan.get("strategy") if recommended_plan else None,
        "selected_count": recommended_metrics.get("selected_count", 0),
        "rejected_count": recommended_metrics.get("rejected_count", 0),
        "shortage_count": recommended_metrics.get("shortage_count", 0),
        "has_shortage": bool(recommended_metrics.get("shortage_total")),
        "llm_used": False,
    }


def _dispatch_comparison(plans: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        plan["strategy"]: {
            "plan_id": plan["plan_id"],
            "success": plan["success"],
            "status": plan["status"],
            "selected_resource_ids": [item.get("resource_id") for item in plan.get("selected_resources", [])],
            "shortage_total": plan.get("summary_metrics", {}).get("shortage_total"),
            "max_eta_minutes": plan.get("summary_metrics", {}).get("max_eta_minutes"),
            "max_risk_score": plan.get("summary_metrics", {}).get("max_risk_score"),
            "warnings": list(plan.get("warnings") or []),
        }
        for plan in plans
    }


def _warnings(task: ResourceAgentTask, plans: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    seen: set[str] = set()
    if not task.resources:
        _append_unique(warnings, seen, "Resource inventory is empty.")
    if plans and not any(plan.get("selected_resources") for plan in plans):
        _append_unique(warnings, seen, "No dispatchable resource was selected by the Resource Calculation Unit.")
    for plan in plans:
        for warning in plan.get("warnings") or []:
            _append_unique(warnings, seen, str(warning))
    return warnings


def _append_unique(values: list[str], seen: set[str], value: str) -> None:
    if value not in seen:
        values.append(value)
        seen.add(value)


def _analysis(
    task: ResourceAgentTask,
    plans: list[dict[str, Any]],
    recommended_plan: dict[str, Any] | None,
    warnings: list[str],
) -> dict[str, Any]:
    if not recommended_plan:
        summary = "No viable dispatch plan was found for the supplied inventory, road network, and resource requirements."
    elif task.mode == "compare":
        summary = (
            f"Compared {len(plans)} real dispatch plans and recommended "
            f"{recommended_plan['strategy']} using deterministic plan-level scoring."
        )
    else:
        summary = f"Prepared a {recommended_plan['strategy']} dispatch plan from the Resource Calculation Unit result."
    return {
        "summary": summary,
        "comparison": _dispatch_comparison(plans),
        "key_factors": _key_factors(recommended_plan),
        "rejection_explanations": recommended_plan.get("rejection_explanations", []) if recommended_plan else [],
        "reasoning": _key_factors(recommended_plan),
        "factors": ["capability match", "resource status", "ETA", "route risk", "terrain and road constraints", "shortage"],
        "warnings": warnings,
        "confidence": None,
    }


def _key_factors(recommended_plan: dict[str, Any] | None) -> list[str]:
    if not recommended_plan:
        return ["No plan selected because every calculated plan had no selected resources."]
    factors = [
        f"Recommended plan {recommended_plan['plan_id']} is one of the calculated dispatch plans.",
        "Selected resources, rejected resources, shortages, ETA, risk, and route geometry are copied from ResourceDispatchResult.",
    ]
    if recommended_plan.get("resource_shortage"):
        factors.append("Minimum requirements are not fully satisfied; shortage details are preserved for command review.")
    if recommended_plan.get("rejected_resources"):
        factors.append("Rejected or unavailable resources remain visible with Resource Calculation Unit reason codes.")
    if any(_uses_air_estimate(resource) for resource in recommended_plan.get("selected_resources", [])):
        factors.append("UAV or air resources use a simplified direct flight-time estimate, not a 3D flight path.")
    return factors


def _uses_air_estimate(resource: Mapping[str, Any]) -> bool:
    route = dict(resource.get("route") or {})
    return route.get("algorithm") == "direct_air_estimate"


def _visualization(task: ResourceAgentTask, recommended_plan: dict[str, Any] | None) -> dict[str, Any]:
    if not recommended_plan:
        return {"layers": [_target_layer(task)], "timeline": [], "annotations": [], "interactions": []}

    layers = [_target_layer(task)]
    selected_ids = {item.get("resource_id") for item in recommended_plan.get("selected_resources") or []}
    for resource in recommended_plan.get("selected_resources") or []:
        point = _resource_point_layer(task, resource, "selected")
        if point:
            layers.append(point)
        route = _resource_route_layer(resource)
        if route:
            layers.append(route)
    for resource in recommended_plan.get("candidate_resources") or []:
        if resource.get("resource_id") in selected_ids:
            continue
        point = _resource_point_layer(task, resource, "candidate")
        if point:
            layers.append(point)
    for resource in recommended_plan.get("rejected_resources") or []:
        point = _resource_point_layer(task, resource, "rejected")
        if point:
            layers.append(point)

    return {
        "layers": layers,
        "timeline": [],
        "annotations": [],
        "interactions": [{"type": "inspect_resource_dispatch", "target": layer["id"]} for layer in layers],
    }


def _target_layer(task: ResourceAgentTask) -> dict[str, Any]:
    target = task.road_network.node(task.task.target_node_id).to_point()
    return {
        "id": f"resource_target_{task.task.target_node_id}",
        "type": "resource_target",
        "layer_type": "resource_target",
        "geometry": {"type": "Point", "coordinates": [target["longitude"], target["latitude"]]},
        "properties": {"target_node_id": task.task.target_node_id, "task_id": task.task.task_id},
    }


def _resource_point_layer(
    task: ResourceAgentTask,
    resource: Mapping[str, Any],
    status: str,
) -> dict[str, Any] | None:
    geometry = _resource_point_geometry(task, resource)
    if not geometry:
        return None
    return {
        "id": f"resource_{status}_{resource.get('resource_id')}",
        "type": "resource_point",
        "layer_type": "resource_point",
        "resource_status": status,
        "geometry": geometry,
        "properties": {
            "resource_id": resource.get("resource_id"),
            "resource_type": resource.get("resource_type"),
            "name": resource.get("name"),
            "status": status,
            "estimated_response_minutes": resource.get("estimated_response_minutes"),
            "risk_score": resource.get("risk_score"),
            "reason_codes": list(resource.get("reason_codes") or []),
        },
    }


def _resource_point_geometry(task: ResourceAgentTask, resource: Mapping[str, Any]) -> dict[str, Any] | None:
    origin = resource.get("origin") or {}
    longitude = origin.get("longitude") or resource.get("longitude")
    latitude = origin.get("latitude") or resource.get("latitude")
    if longitude is None or latitude is None:
        node_id = origin.get("node_id") or resource.get("location_node_id")
        if node_id:
            node = task.road_network.node(str(node_id))
            longitude = node.longitude
            latitude = node.latitude
    if longitude is None or latitude is None:
        return None
    return {"type": "Point", "coordinates": [longitude, latitude]}


def _resource_route_layer(resource: Mapping[str, Any]) -> dict[str, Any] | None:
    route = dict(resource.get("route") or {})
    geometry = route.get("geometry")
    if not geometry:
        return None
    resource_id = resource.get("resource_id")
    return {
        "id": f"resource_route_{resource_id}",
        "type": "resource_route",
        "layer_type": "resource_route",
        "resource_id": resource_id,
        "geometry": geometry,
        "properties": {
            "resource_id": resource_id,
            "resource_type": resource.get("resource_type"),
            "estimated_response_minutes": resource.get("estimated_response_minutes"),
            "risk_score": resource.get("risk_score"),
            "route_edges": route.get("route_edges", []),
            "route_nodes": route.get("route_nodes", []),
            "terrain_metrics": route.get("terrain_metrics", {}),
            "road_metrics": route.get("road_metrics", {}),
            "accessibility": route.get("accessibility", {}),
            "is_simplified_direct_estimate": route.get("algorithm") == "direct_air_estimate",
        },
    }


def _decision(
    task: ResourceAgentTask,
    plans: list[dict[str, Any]],
    recommended_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    constraints = []
    if task.task.blocked_edge_ids:
        constraints.append({"type": "blocked_edges", "edge_ids": sorted(task.task.blocked_edge_ids)})
    if task.task.edge_status_overrides:
        constraints.append({"type": "edge_status_overrides", "values": dict(task.task.edge_status_overrides)})
    if task.task.edge_risk_overrides:
        constraints.append({"type": "edge_risk_overrides", "values": dict(task.task.edge_risk_overrides)})
    return {
        "recommended_dispatch_plan": recommended_plan,
        "recommendation_reason": _recommendation_reason(task.mode, recommended_plan),
        "selected_resources": recommended_plan.get("selected_resources", []) if recommended_plan else [],
        "shortages": recommended_plan.get("resource_shortage", []) if recommended_plan else [],
        "alternatives": [plan for plan in plans if plan is not recommended_plan],
        "constraints": constraints,
        "recommendations": [recommended_plan] if recommended_plan else [],
        "priority": task.task.priority,
        "actions": [],
        "basis": ["Resource Calculation Unit result", "Route Calculation Unit metrics", "deterministic plan-level recommendation"],
    }


def _recommendation_reason(mode: str, recommended_plan: dict[str, Any] | None) -> str:
    if not recommended_plan:
        return "No recommendation is available because no calculated dispatch plan selected a resource."
    if mode == "compare":
        return "Compare mode recommends one calculated plan using deterministic shortage, ETA, risk, and selected-count scoring."
    return f"{mode} mode uses the single calculated ResourceDispatchResult for that strategy."


def _algorithm_output(
    task: ResourceAgentTask,
    plans: list[dict[str, Any]],
    comparison: dict[str, Any],
) -> dict[str, Any]:
    return {
        "result": {
            "mode": task.mode,
            "dispatch_plans": plans,
            "dispatch_comparison": comparison,
        },
        "metrics": {
            "plan_count": len(plans),
            "successful_plan_count": sum(1 for plan in plans if plan.get("success")),
            "inventory_count": len(task.resources),
            "llm_used": False,
        },
        "artifacts": [],
    }


def _provenance(task: ResourceAgentTask, plans: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "source_agent": "ResourceAgent",
        "data_sources": [
            "ResourceAgentTask",
            "ResourceTask",
            "Resource inventory",
            "RoadNetwork",
            "Resource Calculation Unit",
            "Route Calculation Unit",
        ],
        "provider": None,
        "model": None,
        "dispatch_strategies": [plan["strategy"] for plan in plans],
        "resource_source": task.metadata.get("resource_source", "resource_inventory"),
        "network_source": task.metadata.get("network_source") or task.task.metadata.get("network_source", "road_network"),
        "risk_data_source": task.metadata.get("risk_data_source") or task.task.metadata.get("risk_data_source", "edge_risk_score/request_overrides"),
        "llm_used": False,
        "synthetic": bool(task.metadata.get("synthetic") or task.task.metadata.get("synthetic")),
    }


def _reasoning(
    task: ResourceAgentTask,
    plans: list[dict[str, Any]],
    recommended_plan: dict[str, Any] | None,
    warnings: list[str],
) -> list[str]:
    reasoning = [
        "ResourceAgent called the public Resource Calculation Unit entry point for each requested dispatch strategy.",
        "No LLM call was used; recommendations are deterministic and based only on calculated ResourceDispatchResult fields.",
    ]
    if task.mode == "compare":
        reasoning.append("Computed fastest_response, safest_response, capability_first, and balanced dispatch plans for comparison.")
    if recommended_plan:
        reasoning.append(f"Recommended dispatch plan {recommended_plan['plan_id']} is one of the calculated dispatch plans.")
    reasoning.extend(warnings)
    return reasoning
