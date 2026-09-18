"""Commander decision agent."""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.agents.base import AgentResult, BaseAgent, agent_result
from app.agents.context import AgentAnalysisContext


def build_structured_command_summary(
    *,
    situation_summary: Mapping[str, Any] | None = None,
    spread_summary: Mapping[str, Any] | None = None,
    risk_summary: Mapping[str, Any] | None = None,
    planning_summary: Mapping[str, Any] | None = None,
    input_summary: Mapping[str, Any] | None = None,
) -> str:
    source = input_summary or {}
    if spread_summary:
        source = {
            **source,
            "final_area_km2": spread_summary.get("final_area_km2"),
            "max_radius_km": spread_summary.get("max_radius_km"),
            "wind_speed_m_s": spread_summary.get("environment", {}).get("wind_speed_m_s"),
            "wind_direction_deg": spread_summary.get("environment", {}).get("wind_direction_deg"),
            "fire_weather_index": spread_summary.get("environment", {}).get("fire_weather_index"),
        }
    if risk_summary:
        source = {
            **source,
            "risk_level": risk_summary.get("risk_level"),
        }
    event_name = (situation_summary or {}).get("event", {}).get("name") or source.get("event_name", "Current fire event")
    summary = (
        f"{event_name}: projected burned area is about {source.get('final_area_km2', '--')} km2; "
        f"risk level is {source.get('risk_level', '--')}. "
        "Prioritize downwind reconnaissance, protected-target resource pre-positioning, "
        "and evacuation route readiness."
    )
    if planning_summary:
        selected = planning_summary.get("selected_resources") or []
        eta = planning_summary.get("eta_minutes") or {}
        selected_ids = ", ".join(str(item.get("resource_id")) for item in selected) or "none"
        summary = (
            f"{summary} Planning status is {planning_summary.get('status', '--')}; "
            f"selected resources: {selected_ids}; "
            f"earliest ETA {eta.get('earliest')}, max ETA {eta.get('max')} minutes."
        )
    return summary


def _priority_for_risk(risk_level: str) -> str:
    return "critical" if risk_level == "high" else "high" if risk_level == "medium" else "normal"


def _score_for_risk(risk_level: str) -> int:
    return 91 if risk_level == "high" else 84 if risk_level == "medium" else 76


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_llm_summary(content: str) -> str | None:
    try:
        parsed = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return None
    if isinstance(parsed, dict) and isinstance(parsed.get("summary"), str):
        return parsed["summary"]
    return None


def build_planning_summary(planning_result: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Create a compact deterministic Commander input from PlanningResult facts."""
    if not planning_result:
        return None
    selected = list(planning_result.get("selected_resources") or [])
    operational_routes = list(planning_result.get("operational_routes") or [])
    shortages = list(planning_result.get("resource_shortage") or [])
    eta_values = [route.get("eta_minutes") for route in operational_routes if route.get("eta_minutes") is not None]
    risk_values = [route.get("risk_score") for route in operational_routes if route.get("risk_score") is not None]
    return {
        "status": planning_result.get("status"),
        "success": planning_result.get("success"),
        "task": dict(planning_result.get("task") or {}),
        "selected_resource_count": len(selected),
        "selected_resources": [
            {
                "resource_id": item.get("resource_id"),
                "resource_type": item.get("resource_type"),
                "name": item.get("name"),
                "estimated_response_minutes": item.get("estimated_response_minutes"),
                "risk_score": item.get("risk_score"),
            }
            for item in selected
        ],
        "operational_route_count": len(operational_routes),
        "operational_routes": [
            {
                "resource_id": item.get("resource_id"),
                "route_source": item.get("route_source"),
                "eta_minutes": item.get("eta_minutes"),
                "risk_score": item.get("risk_score"),
                "distance_km": item.get("distance_km"),
                "geometry": item.get("geometry"),
            }
            for item in operational_routes
        ],
        "alternative_route_count": len(planning_result.get("alternative_routes") or []),
        "eta_minutes": {
            "earliest": min(eta_values) if eta_values else None,
            "max": max(eta_values) if eta_values else None,
        },
        "route_risk": {
            "min": min(risk_values) if risk_values else None,
            "max": max(risk_values) if risk_values else None,
        },
        "shortage": {
            "items": [
                {
                    "resource_type": item.get("resource_type"),
                    "required": item.get("required"),
                    "available": item.get("available"),
                    "shortage": item.get("shortage"),
                }
                for item in shortages
            ],
            "total": sum(int(item.get("shortage") or 0) for item in shortages),
        },
        "warnings": list(planning_result.get("warnings") or []),
        "diagnostics": dict(planning_result.get("diagnostics") or {}),
    }


def _planning_actions(planning_summary: Mapping[str, Any] | None) -> list[str]:
    if not planning_summary:
        return []
    if planning_summary.get('status') == 'unavailable':
        return [
            'Obtain a verified resource inventory before issuing dispatch orders.',
            'Load a validated road network before recommending operational routes.',
        ]
    actions: list[str] = []
    selected = list(planning_summary.get("selected_resources") or [])
    routes = list(planning_summary.get("operational_routes") or [])
    if selected:
        actions.append(
            "Dispatch selected planning resources: "
            + ", ".join(str(item.get("resource_id")) for item in selected)
            + "."
        )
    for route in routes:
        actions.append(
            "Use operational route for "
            f"{route.get('resource_id')} with ETA {route.get('eta_minutes')} min "
            f"and route risk {route.get('risk_score')}."
        )
    shortage = dict(planning_summary.get("shortage") or {})
    if shortage.get("total"):
        actions.append(f"Escalate resource shortage total {shortage.get('total')} for command review.")
    return actions


def _planning_reasons(planning_summary: Mapping[str, Any] | None) -> list[str]:
    if not planning_summary:
        return []
    reasons = [
        f"Planning status: {planning_summary.get('status')}",
        f"Selected resource count: {planning_summary.get('selected_resource_count')}",
        f"Operational route count: {planning_summary.get('operational_route_count')}",
    ]
    eta = dict(planning_summary.get("eta_minutes") or {})
    risk = dict(planning_summary.get("route_risk") or {})
    if eta.get("earliest") is not None or eta.get("max") is not None:
        reasons.append(f"Planning ETA minutes: earliest {eta.get('earliest')}, max {eta.get('max')}")
    if risk.get("min") is not None or risk.get("max") is not None:
        reasons.append(f"Planning route risk: min {risk.get('min')}, max {risk.get('max')}")
    shortage = dict(planning_summary.get("shortage") or {})
    if shortage.get("total"):
        reasons.append(f"Resource shortage total: {shortage.get('total')}")
    return reasons


class CommanderAgent(BaseAgent):
    agent_name = "CommanderAgent"

    def __init__(self, llm_provider: Any | None = None) -> None:
        self.llm_provider = llm_provider

    async def run(
        self,
        analysis_context: AgentAnalysisContext | Mapping[str, Any],
        planning_result: Mapping[str, Any] | None = None,
        force_provider: str | None = None,
    ) -> AgentResult:
        analysis = analysis_context.to_dict() if hasattr(analysis_context, "to_dict") else dict(analysis_context)
        situation = analysis.get("situation", {})
        spread = analysis.get("spread", {})
        risk = analysis.get("risk", {})
        situation_summary = situation.get("situation_summary", {})
        spread_summary = spread.get("spread_summary", {})
        risk_summary = risk.get("risk_summary", {})
        risk_level = risk.get("risk_level") or risk_summary.get("risk_level") or "low"
        warnings = risk.get("warnings", [])
        final_area = _number(spread_summary.get("final_area_km2"))
        wind_speed = _number(spread_summary.get("environment", {}).get("wind_speed_m_s"))
        wind_direction = _number(spread_summary.get("environment", {}).get("wind_direction_deg"))
        fire_weather_index = _number(spread_summary.get("environment", {}).get("fire_weather_index"))
        planning_summary = build_planning_summary(planning_result)
        planning_actions = _planning_actions(planning_summary)
        planning_reasons = _planning_reasons(planning_summary)
        planning_warnings = list(planning_summary.get("warnings") or []) if planning_summary else []

        recommended_plan = {
            "plan_id": "plan_priority_containment_recon",
            "name": (
                "Route-resource coordinated incident response"
                if planning_summary and planning_summary.get('success')
                else "Downwind reconnaissance and protected-target pre-positioning"
            ),
            "score": _score_for_risk(risk_level),
            "priority": _priority_for_risk(risk_level),
            "actions": [
                "Dispatch UAV reconnaissance along the downwind axis.",
                "Pre-position suppression resources near protected targets.",
                "Keep evacuation and route clearance plans ready for escalation.",
            ]
            + planning_actions,
            "strategy": "Use the trusted fire point as the decision anchor; verify downwind fireline growth, pre-position protected-target resources, and keep evacuation routes available.",
            "reasons": [
                f"Projected final area: {final_area:.2f} km2",
                f"Wind speed {wind_speed:.1f} m/s, direction {wind_direction:.0f} deg",
                f"Fire weather index {fire_weather_index:.1f}",
            ]
            + planning_reasons,
        }
        recommended_plan['provenance'] = dict(analysis.get('provenance') or {})
        recommended_plan['capabilities'] = dict(analysis.get('capabilities') or {})
        if planning_summary:
            recommended_plan["planning_status"] = planning_summary.get("status")
            recommended_plan["selected_resources"] = planning_summary["selected_resources"]
            recommended_plan["operational_routes"] = planning_summary["operational_routes"]
            recommended_plan["resource_shortage"] = planning_summary["shortage"]
            recommended_plan["planning_warnings"] = planning_warnings
        plan_packet = {
            "recommended_plan": recommended_plan,
            "candidate_plans": [
                recommended_plan,
                {"plan_id": "plan_recon_first", "name": "Reconnaissance-first plan", "score": max(60, recommended_plan["score"] - 7)},
                {"plan_id": "plan_resource_forward", "name": "Resource-forward plan", "score": max(60, recommended_plan["score"] - 10)},
            ],
        }
        fallback_summary = build_structured_command_summary(
            situation_summary=situation_summary,
            spread_summary=spread_summary,
            risk_summary=risk_summary,
            planning_summary=planning_summary,
        )
        provider_name = "structured"
        model_name = "structured-command-rules"
        raw_llm_output = fallback_summary
        used_remote = False
        summary = fallback_summary

        llm_payload = {
            "situation_summary": situation_summary,
            "spread_summary": spread_summary,
            "risk_summary": risk_summary,
            "planning_summary": planning_summary,
        }
        try:
            provider = self.llm_provider
            if provider is None:
                from app.llm.providers import get_llm_provider

                provider = get_llm_provider(force_provider)
            llm = await provider.generate(
                "Return strict JSON only with this shape: {\"summary\":\"...\"}. Use only supplied wildfire analysis and planning summary data. Do not invent or change planning facts, routes, resources, ETA, risk, or shortage values.",
                llm_payload,
            )
            provider_name = getattr(llm, "provider", getattr(provider, "provider_name", provider_name))
            model_name = getattr(llm, "model", getattr(provider, "model", model_name))
            raw_llm_output = getattr(llm, "content", fallback_summary)
            used_remote = bool(getattr(llm, "used_remote", False))
            summary = _parse_llm_summary(raw_llm_output) or fallback_summary
        except Exception as exc:
            if planning_summary:
                raw_llm_output = fallback_summary
                used_remote = False
                summary = fallback_summary
            else:
                try:
                    from app.llm.providers import StructuredFallbackProvider

                    fallback = await StructuredFallbackProvider().generate(
                        "Generate a structured fallback wildfire command summary.",
                        {
                            "input_summary": {
                                "final_area_km2": final_area,
                                "risk_level": risk_level,
                                "wind_speed_m_s": wind_speed,
                                "fire_weather_index": fire_weather_index,
                            }
                        },
                    )
                    provider_name = fallback.provider
                    model_name = fallback.model
                    raw_llm_output = fallback.content
                    used_remote = False
                    summary = _parse_llm_summary(raw_llm_output) or fallback_summary
                except Exception:
                    raw_llm_output = f"{fallback_summary} CommanderAgent LLM fallback reason: {exc}"

        recommendation_packet = {
            "summary": summary,
            "recommended_plan": recommended_plan,
            "warnings": list(warnings) + planning_warnings,
        }
        if planning_summary:
            plan_packet["planning_summary"] = planning_summary
            plan_packet["planning_result"] = dict(planning_result or {})
            recommendation_packet["planning_summary"] = planning_summary

        output = {
            "plan_packet": plan_packet,
            "recommendation_packet": recommendation_packet,
            "recommended_plan": recommended_plan,
            "llm": {
                "provider": provider_name,
                "model": model_name,
                "used_remote": used_remote,
                "raw_output": raw_llm_output,
            },
            "decision_summary": {
                "risk_level": risk_level,
                "warning_count": len(warnings) + len(planning_warnings),
                "summary": summary,
                "planning_summary": planning_summary,
            },
        }

        return agent_result(
            self.agent_name,
            output=output,
            reasoning=[
                "Generated plan and recommendation packets from AgentAnalysisContext.",
                "LLM output is limited to a JSON summary; plan structure remains deterministic.",
            ],
        )
