"""Standard Agent output protocol and adapters.

This module keeps the legacy AgentResult shape intact while providing a
command-system friendly envelope for algorithms, analysis, visualization, and
decision output.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, TypedDict


SCHEMA_VERSION = "agent-output/v1"


class AgentStandardOutput(TypedDict):
    schema_version: str
    agent_name: str
    domain: str
    status: str
    generated_at: str
    legacy_output: dict[str, Any]
    algorithm: dict[str, Any]
    analysis: dict[str, Any]
    visualization: dict[str, Any]
    decision: dict[str, Any]
    provenance: dict[str, Any]


def standardize_agent_result(result: Mapping[str, Any]) -> AgentStandardOutput:
    agent_name = str(result.get("agent_name") or "UnknownAgent")
    output = dict(result.get("output") or {})
    reasoning = list(result.get("reasoning") or [])
    status = str(result.get("status") or "unknown")

    if agent_name == "SituationAgent":
        return _situation_output(agent_name, status, output, reasoning)
    if agent_name == "SpreadAgent":
        return _spread_output(agent_name, status, output, reasoning)
    if agent_name == "RiskAgent":
        return _risk_output(agent_name, status, output, reasoning)
    if agent_name == "RouteAgent":
        return _route_output(agent_name, status, output, reasoning)
    if agent_name == "ResourceAgent":
        return _resource_output(agent_name, status, output, reasoning)
    if agent_name == "CommanderAgent":
        return _commander_output(agent_name, status, output, reasoning)
    return _base_output(agent_name, status, "generic", output, reasoning)


def standardize_agent_results(results: list[Mapping[str, Any]]) -> list[AgentStandardOutput]:
    return [standardize_agent_result(result) for result in results]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _base_output(
    agent_name: str,
    status: str,
    domain: str,
    legacy_output: dict[str, Any],
    reasoning: list[str],
    *,
    algorithm: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
    visualization: dict[str, Any] | None = None,
    decision: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
) -> AgentStandardOutput:
    return {
        "schema_version": SCHEMA_VERSION,
        "agent_name": agent_name,
        "domain": domain,
        "status": status,
        "generated_at": _now(),
        "legacy_output": legacy_output,
        "algorithm": algorithm or {"result": legacy_output, "metrics": {}, "artifacts": []},
        "analysis": analysis or {"summary": "", "reasoning": reasoning, "factors": [], "warnings": [], "confidence": None},
        "visualization": visualization or {"layers": [], "timeline": [], "annotations": [], "interactions": []},
        "decision": decision or {"recommendations": [], "priority": None, "actions": [], "constraints": [], "basis": []},
        "provenance": provenance or {"source_agent": agent_name, "data_sources": [], "provider": None, "model": None},
    }


def _point_geometry(point: Mapping[str, Any]) -> dict[str, Any] | None:
    longitude = point.get("longitude")
    latitude = point.get("latitude")
    if longitude is None or latitude is None:
        return None
    return {"type": "Point", "coordinates": [longitude, latitude]}


def _situation_output(
    agent_name: str,
    status: str,
    output: dict[str, Any],
    reasoning: list[str],
) -> AgentStandardOutput:
    packet = output.get("situation_packet", {})
    summary = output.get("situation_summary", {})
    trusted_point = packet.get("trusted_point", {})
    environment = packet.get("environment", {})
    geometry = _point_geometry(trusted_point)
    layers = []
    if geometry:
        layers.append(
            {
                "id": "trusted_fire_point",
                "type": "point",
                "geometry": geometry,
                "style": {"color": "#ef4444", "icon": "flame"},
                "label": "Trusted fire point",
                "properties": trusted_point,
            }
        )

    return _base_output(
        agent_name,
        status,
        "situation",
        output,
        reasoning,
        algorithm={"result": packet, "metrics": {"confidence": trusted_point.get("confidence")}, "artifacts": []},
        analysis={
            "summary": packet.get("summary", ""),
            "reasoning": reasoning,
            "factors": ["trusted fire point", "environment snapshot", "fusion result"],
            "warnings": [],
            "confidence": trusted_point.get("confidence"),
        },
        visualization={
            "layers": layers,
            "timeline": [],
            "annotations": [
                {
                    "id": "wind",
                    "type": "wind",
                    "text": f"Wind {environment.get('wind_speed_m_s', '--')} m/s @ {environment.get('wind_direction_deg', '--')} deg",
                    "properties": environment,
                }
            ],
            "interactions": [{"type": "inspect", "target": "trusted_fire_point"}] if geometry else [],
        },
        provenance={"source_agent": agent_name, "data_sources": ["FireEvent", "TrustedFirePoint", "EnvironmentSnapshot", "FusionResult"], "provider": None, "model": None},
    )


def _spread_output(
    agent_name: str,
    status: str,
    output: dict[str, Any],
    reasoning: list[str],
) -> AgentStandardOutput:
    packet = output.get("spread_packet", {})
    summary = output.get("spread_summary", {})
    steps = list(summary.get("fire_front_steps") or [])
    timeline = [
        {
            "time_minute": step.get("time_minute"),
            "elapsed_seconds": step.get("elapsed_seconds"),
            "metrics": {
                "area_km2": step.get("area_km2"),
                "radius_km": step.get("radius_km"),
                "spread_direction_deg": step.get("spread_direction_deg"),
            },
            "geometry": step.get("fireline_geojson"),
        }
        for step in steps
    ]

    return _base_output(
        agent_name,
        status,
        "spread",
        output,
        reasoning,
        algorithm={
            "result": packet,
            "metrics": {
                "final_area_km2": packet.get("final_area_km2"),
                "max_radius_km": packet.get("max_radius_km"),
                "avg_growth_km2_per_hour": summary.get("avg_growth_km2_per_hour"),
                "step_count": packet.get("step_count"),
            },
            "artifacts": [{"type": "simulation_run", "id": packet.get("run_id")}],
        },
        analysis={
            "summary": (
                f"Spread reaches about {packet.get('final_area_km2', '--')} km2 "
                f"with max radius {packet.get('max_radius_km', '--')} km."
            ),
            "reasoning": reasoning,
            "factors": ["fire front steps", "spread engine", "wind field", "trusted point"],
            "warnings": ["Fallback spread engine used."] if packet.get("fallback_used") else [],
            "confidence": None,
        },
        visualization={
            "layers": [
                {
                    "id": "fire_front_timeline",
                    "type": "temporal_fire_front",
                    "timeline": timeline,
                    "style": {"color": "#f97316", "fillColor": "#ef4444", "opacity": 0.35},
                },
                {
                    "id": "spread_direction",
                    "type": "direction",
                    "value_deg": summary.get("spread_direction_deg"),
                    "style": {"color": "#f59e0b"},
                },
            ],
            "timeline": timeline,
            "annotations": [],
            "interactions": [{"type": "scrub_time", "target": "fire_front_timeline"}],
        },
        provenance={"source_agent": agent_name, "data_sources": ["SimulationRun", "FireFrontStep", "EnvironmentSnapshot", "TrustedFirePoint"], "provider": None, "model": None},
    )


def _risk_output(
    agent_name: str,
    status: str,
    output: dict[str, Any],
    reasoning: list[str],
) -> AgentStandardOutput:
    packet = output.get("risk_packet", {})
    summary = output.get("risk_summary", {})
    warnings = list(output.get("warnings") or summary.get("warnings") or [])

    return _base_output(
        agent_name,
        status,
        "risk",
        output,
        reasoning,
        algorithm={
            "result": packet,
            "metrics": {
                "risk_level": output.get("risk_level"),
                "final_area_km2": summary.get("final_area_km2"),
                "max_radius_km": summary.get("max_radius_km"),
                "fire_weather_index": summary.get("fire_weather_index"),
            },
            "artifacts": [],
        },
        analysis={
            "summary": packet.get("summary", ""),
            "reasoning": reasoning,
            "factors": list(output.get("risk_factors") or packet.get("drivers") or []),
            "warnings": warnings,
            "confidence": summary.get("trusted_point_confidence"),
        },
        visualization={
            "layers": [
                {
                    "id": "risk_level",
                    "type": "status_badge",
                    "value": output.get("risk_level"),
                    "style": {"palette": "risk"},
                }
            ],
            "timeline": [],
            "annotations": [{"id": f"warning_{index}", "type": "warning", "text": warning} for index, warning in enumerate(warnings)],
            "interactions": [{"type": "show_drivers", "target": "risk_level"}],
        },
        provenance={"source_agent": agent_name, "data_sources": ["RiskAgent rules", "SpreadAgent output"], "provider": None, "model": None},
    )


def _route_output(
    agent_name: str,
    status: str,
    output: dict[str, Any],
    reasoning: list[str],
) -> AgentStandardOutput:
    candidates = list(output.get("candidate_routes") or [])
    recommended = output.get("recommended_route")
    route_summary = output.get("route_summary", {})
    warnings = list(output.get("warnings") or [])

    return _base_output(
        agent_name,
        status,
        "route",
        output,
        reasoning,
        algorithm=output.get("algorithm") or {
            "result": {
                "route_summary": route_summary,
                "candidate_routes": candidates,
                "route_comparison": output.get("route_comparison", {}),
            },
            "metrics": {
                "candidate_count": len(candidates),
                "reachable_candidate_count": sum(1 for candidate in candidates if candidate.get("success")),
            },
            "artifacts": [],
        },
        analysis=output.get("analysis") or {
            "summary": route_summary.get("status", ""),
            "reasoning": reasoning,
            "factors": ["distance", "ETA", "risk", "terrain", "road condition", "accessibility"],
            "warnings": warnings,
            "confidence": None,
        },
        visualization=output.get("visualization") or {
            "layers": [
                {
                    "id": candidate.get("route_id"),
                    "type": "route",
                    "layer_type": "route",
                    "route_role": candidate.get("objective"),
                    "geometry": candidate.get("geometry"),
                    "properties": candidate,
                }
                for candidate in candidates
                if candidate.get("success")
            ],
            "timeline": [],
            "annotations": [],
            "interactions": [],
        },
        decision=output.get("decision") or {
            "recommended_route": recommended,
            "recommendations": [recommended] if recommended else [],
            "priority": None,
            "actions": [],
            "constraints": [],
            "basis": ["Route Calculation Unit result"],
        },
        provenance=output.get("provenance") or {
            "source_agent": agent_name,
            "data_sources": ["RouteTask", "Route Calculation Unit"],
            "provider": None,
            "model": None,
        },
    )


def _resource_output(
    agent_name: str,
    status: str,
    output: dict[str, Any],
    reasoning: list[str],
) -> AgentStandardOutput:
    plans = list(output.get("dispatch_plans") or [])
    recommended = output.get("recommended_plan")
    resource_summary = output.get("resource_summary", {})
    warnings = list(output.get("warnings") or [])

    return _base_output(
        agent_name,
        status,
        "resource",
        output,
        reasoning,
        algorithm=output.get("algorithm") or {
            "result": {
                "resource_summary": resource_summary,
                "dispatch_plans": plans,
                "dispatch_comparison": output.get("dispatch_comparison", {}),
            },
            "metrics": {
                "plan_count": len(plans),
                "successful_plan_count": sum(1 for plan in plans if plan.get("success")),
                "inventory_count": resource_summary.get("inventory_count"),
                "llm_used": False,
            },
            "artifacts": [],
        },
        analysis=output.get("analysis") or {
            "summary": resource_summary.get("status", ""),
            "reasoning": reasoning,
            "factors": ["capability match", "resource status", "ETA", "risk", "route geometry", "shortage"],
            "warnings": warnings,
            "confidence": None,
        },
        visualization=output.get("visualization") or {
            "layers": [],
            "timeline": [],
            "annotations": [],
            "interactions": [],
        },
        decision=output.get("decision") or {
            "recommended_dispatch_plan": recommended,
            "recommendations": [recommended] if recommended else [],
            "priority": None,
            "actions": [],
            "constraints": [],
            "basis": ["Resource Calculation Unit result"],
        },
        provenance=output.get("provenance") or {
            "source_agent": agent_name,
            "data_sources": ["ResourceAgentTask", "Resource Calculation Unit"],
            "provider": None,
            "model": None,
        },
    )
def _commander_output(
    agent_name: str,
    status: str,
    output: dict[str, Any],
    reasoning: list[str],
) -> AgentStandardOutput:
    plan = output.get("recommended_plan", {})
    recommendation_packet = output.get("recommendation_packet", {})
    llm = output.get("llm", {})

    return _base_output(
        agent_name,
        status,
        "command",
        output,
        reasoning,
        algorithm={"result": output.get("plan_packet", {}), "metrics": {"score": plan.get("score")}, "artifacts": []},
        analysis={
            "summary": recommendation_packet.get("summary") or output.get("decision_summary", {}).get("summary", ""),
            "reasoning": reasoning,
            "factors": list(plan.get("reasons") or []),
            "warnings": list(recommendation_packet.get("warnings") or []),
            "confidence": None,
        },
        visualization={
            "layers": [
                {
                    "id": "recommended_plan",
                    "type": "decision_panel",
                    "properties": plan,
                }
            ],
            "timeline": [],
            "annotations": [],
            "interactions": [{"type": "approve_or_recalculate", "target": "recommended_plan"}],
        },
        decision={
            "recommendations": [plan] if plan else [],
            "priority": plan.get("priority"),
            "actions": list(plan.get("actions") or []),
            "constraints": [],
            "basis": list(plan.get("reasons") or []),
        },
        provenance={"source_agent": agent_name, "data_sources": ["AgentAnalysisContext"], "provider": llm.get("provider"), "model": llm.get("model")},
    )
