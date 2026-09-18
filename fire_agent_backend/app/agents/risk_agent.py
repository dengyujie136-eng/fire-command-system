"""Rule-based risk assessment agent."""

from __future__ import annotations

from typing import Mapping

from app.agents.base import AgentResult, BaseAgent, agent_result
from app.agents.context import AgentContext
from app.integrations.schemas import IncidentContext


def _risk_level(area_km2: float, fire_weather_index: float, confidence: float) -> str:
    if area_km2 >= 4.5 or fire_weather_index >= 24 or confidence >= 0.9:
        return "high"
    if area_km2 >= 1.2 or fire_weather_index >= 14 or confidence >= 0.78:
        return "medium"
    return "low"


def _risk_label(level: str) -> str:
    return {"high": "high", "medium": "medium", "low": "low"}.get(level, level)


def _round(value: float, digits: int = 3) -> float:
    return round(float(value), digits)


class RiskAgent(BaseAgent):
    agent_name = "RiskAgent"

    def run(
        self,
        context: AgentContext,
        prior_results: Mapping[str, AgentResult] | None = None,
    ) -> AgentResult:
        if isinstance(context, IncidentContext):
            summary = dict(context.spatial.run.summary or {})
            risk_areas = dict(summary.get('risk_areas') or {})
            if int(risk_areas.get('high_count') or 0) > 0:
                level = 'high'
            elif int(risk_areas.get('medium_count') or 0) > 0:
                level = 'medium'
            else:
                level = context.spread.run.risk_level or 'low'
            affected = [item for item in context.spatial.impacts if item.affected]
            warnings = list(context.spatial.run.warnings or [])
            risk_packet = {
                'risk_level': level,
                'risk_label': _risk_label(level),
                'summary': (
                    f'Spatial analysis {context.spatial.run.analysis_id} identified '
                    f'{len(affected)} affected objects.'
                ),
                'drivers': ['member_c_spatial_analysis'],
                'spread': {'run_id': context.spread.run.run_id},
            }
            risk_summary = {
                'analysis_id': context.spatial.run.analysis_id,
                'spread_run_id': context.spatial.run.spread_run_id,
                'risk_level': level,
                'risk_label': _risk_label(level),
                'risk_areas': risk_areas,
                'affected_object_count': len(affected),
                'impact_record_count': len(context.spatial.impacts),
                'route_count': len(context.spatial.routes),
                'analysis_engine': context.spatial.run.analysis_engine,
                'warnings': warnings,
            }
            return agent_result(
                self.agent_name,
                output={
                    'risk_packet': risk_packet,
                    'risk_summary': risk_summary,
                    'risk_level': level,
                    'risk_label': _risk_label(level),
                    'risk_factors': ['member_c_spatial_analysis'],
                    'warnings': warnings,
                },
                reasoning=[
                    'Interpreted the persisted member C spatial analysis.',
                    'RiskAgent did not recompute spatial risk from area or weather rules.',
                ],
            )

        spread_result = (prior_results or {}).get("SpreadAgent", {})
        spread_output = spread_result.get("output", {}) if spread_result else {}
        spread_packet = spread_output.get("spread_packet")
        spread_summary = spread_output.get("spread_summary", {})
        steps = sorted(context.fire_front_steps, key=lambda step: step.time_minute)
        final_step = steps[-1] if steps else None
        if spread_packet:
            final_area = float(spread_packet.get("final_area_km2") or 0)
            max_radius = float(spread_packet.get("max_radius_km") or 0)
            step_count = int(spread_packet.get("step_count") or len(steps))
        else:
            final_area = float(
                context.spread_run.final_area_km2
                or (final_step.area_km2 if final_step else 0)
                or 0
            )
            max_radius = float(
                context.spread_run.max_radius_km
                or (final_step.radius_km if final_step else 0)
                or 0
            )
            step_count = len(steps)
            spread_packet = {
                "run_id": context.spread_run.run_id,
                "engine": context.spread_run.engine,
                "fallback_used": context.spread_run.fallback_used,
                "step_count": step_count,
                "final_area_km2": _round(final_area, 3),
                "max_radius_km": _round(max_radius, 3),
            }
        environment = context.environment_snapshot
        confidence = context.trusted_fire_point.confidence or 0

        level = _risk_level(
            final_area,
            environment.fire_weather_index or 0,
            confidence,
        )
        risk_factors = ["wind", "fuel moisture", "fire weather index", "trusted point confidence"]
        warnings: list[str] = []
        if context.spread_run.fallback_used:
            warnings.append("ForeFire is unavailable for this run; simplified spread fallback was used.")
        if (environment.wind_speed_m_s or 0) >= 5:
            warnings.append("Wind speed is high; monitor downwind fireline expansion closely.")
        if (environment.humidity_percent or 100) <= 30:
            warnings.append("Humidity is low; dry fuel risk is elevated.")

        risk_packet = {
            "risk_level": level,
            "risk_label": _risk_label(level),
            "summary": f"Projected burned area is about {final_area:.2f} km2 within {context.spread_run.horizon_minutes} minutes; max radius is about {max_radius:.2f} km.",
            "drivers": risk_factors,
            "spread": spread_packet,
        }
        risk_summary = {
            "risk_level": level,
            "risk_label": _risk_label(level),
            "risk_factors": risk_factors,
            "warnings": warnings,
            "final_area_km2": _round(final_area, 3),
            "max_radius_km": _round(max_radius, 3),
            "avg_growth_km2_per_hour": spread_summary.get("avg_growth_km2_per_hour"),
            "step_count": step_count,
            "fire_weather_index": environment.fire_weather_index,
            "trusted_point_confidence": confidence,
        }

        return agent_result(
            self.agent_name,
            output={
                "risk_packet": risk_packet,
                "risk_summary": risk_summary,
                "risk_level": level,
                "risk_label": _risk_label(level),
                "risk_factors": risk_factors,
                "warnings": warnings,
            },
            reasoning=[
                "Built a risk packet compatible with the legacy decision_service output.",
                "Used SpreadAgent output when available, with context-derived spread values as fallback.",
                "Risk can later be replaced by a dedicated model or LLM-assisted evaluator.",
            ],
        )
