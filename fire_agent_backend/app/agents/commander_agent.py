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
    return (
        f"{event_name}: projected burned area is about {source.get('final_area_km2', '--')} km2; "
        f"risk level is {source.get('risk_level', '--')}. "
        "Prioritize downwind reconnaissance, protected-target resource pre-positioning, "
        "and evacuation route readiness."
    )


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


class CommanderAgent(BaseAgent):
    agent_name = "CommanderAgent"

    def __init__(self, llm_provider: Any | None = None) -> None:
        self.llm_provider = llm_provider

    async def run(
        self,
        analysis_context: AgentAnalysisContext | Mapping[str, Any],
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

        recommended_plan = {
            "plan_id": "plan_priority_containment_recon",
            "name": "Downwind reconnaissance and protected-target pre-positioning",
            "score": _score_for_risk(risk_level),
            "priority": _priority_for_risk(risk_level),
            "actions": [
                "Dispatch UAV reconnaissance along the downwind axis.",
                "Pre-position suppression resources near protected targets.",
                "Keep evacuation and route clearance plans ready for escalation.",
            ],
            "strategy": "Use the trusted fire point as the decision anchor; verify downwind fireline growth, pre-position protected-target resources, and keep evacuation routes available.",
            "reasons": [
                f"Projected final area: {final_area:.2f} km2",
                f"Wind speed {wind_speed:.1f} m/s, direction {wind_direction:.0f} deg",
                f"Fire weather index {fire_weather_index:.1f}",
            ],
        }
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
        }
        try:
            provider = self.llm_provider
            if provider is None:
                from app.llm.providers import get_llm_provider

                provider = get_llm_provider(force_provider)
            llm = await provider.generate(
                "Return strict JSON only with this shape: {\"summary\":\"...\"}. Use only supplied wildfire analysis data and do not invent numbers.",
                llm_payload,
            )
            provider_name = getattr(llm, "provider", getattr(provider, "provider_name", provider_name))
            model_name = getattr(llm, "model", getattr(provider, "model", model_name))
            raw_llm_output = getattr(llm, "content", fallback_summary)
            used_remote = bool(getattr(llm, "used_remote", False))
            summary = _parse_llm_summary(raw_llm_output) or fallback_summary
        except Exception as exc:
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
            "warnings": warnings,
        }

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
                "warning_count": len(warnings),
                "summary": summary,
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
