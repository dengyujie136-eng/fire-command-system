"""Rule-based spread analysis agent."""

from __future__ import annotations

from typing import Any, Mapping

from app.agents.base import AgentResult, BaseAgent, agent_result
from app.agents.context import AgentContext
from app.integrations.schemas import IncidentContext


def _round(value: float | None, digits: int = 3) -> float | None:
    return round(float(value), digits) if value is not None else None


def _step_summary(step) -> dict[str, Any]:
    return {
        "step_id": step.step_id,
        "time_minute": step.time_minute,
        "elapsed_seconds": step.elapsed_seconds,
        "area_km2": _round(step.area_km2),
        "radius_km": _round(step.radius_km),
        "spread_direction_deg": step.spread_direction_deg,
        "fireline_geojson": step.fireline_geojson,
        "has_fireline_geojson": bool(step.fireline_geojson),
    }


class SpreadAgent(BaseAgent):
    agent_name = "SpreadAgent"

    def run(
        self,
        context: AgentContext,
        prior_results: Mapping[str, AgentResult] | None = None,
    ) -> AgentResult:
        if isinstance(context, IncidentContext):
            run = context.spread.run
            steps = sorted(context.spread.steps, key=lambda step: step.time_minute)
            final_step = steps[-1] if steps else None
            final_area = float(run.final_area_km2 or 0)
            max_radius = float(run.max_radius_km or 0)
            spread_packet = {
                'run_id': run.run_id,
                'engine': run.engine,
                'fallback_used': run.fallback_used,
                'step_count': len(steps),
                'final_area_km2': _round(final_area),
                'max_radius_km': _round(max_radius),
            }
            environment = context.weather[0].model_dump() if context.weather else {}
            spread_summary = {
                **spread_packet,
                'status': run.status,
                'horizon_minutes': run.horizon_minutes,
                'step_minutes': run.step_minutes,
                'spread_direction_deg': run.spread_direction_deg,
                'risk_level': run.risk_level,
                'environment': environment,
                'input_source': run.input_snapshot.get('ignition_point', {}).get('input_source'),
                'confirmation_id': context.ignition.confirmation_id,
                'final_step': _step_summary(final_step) if final_step else None,
                'fire_front_steps': [_step_summary(step) for step in steps],
            }
            return agent_result(
                self.agent_name,
                output={'spread_packet': spread_packet, 'spread_summary': spread_summary},
                reasoning=[
                    'Summarized the persisted member C spread result.',
                    'SpreadAgent did not calculate or approximate a fire front.',
                ],
            )

        steps = sorted(context.fire_front_steps, key=lambda step: step.time_minute)
        final_step = steps[-1] if steps else None
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
        avg_growth = final_area / max(0.5, context.spread_run.horizon_minutes / 60)

        spread_packet = {
            "run_id": context.spread_run.run_id,
            "engine": context.spread_run.engine,
            "fallback_used": context.spread_run.fallback_used,
            "step_count": len(steps),
            "final_area_km2": _round(final_area),
            "max_radius_km": _round(max_radius),
        }

        spread_summary = {
            **spread_packet,
            "run_id": context.spread_run.run_id,
            "engine": context.spread_run.engine,
            "status": context.spread_run.status,
            "forefire_attempted": context.spread_run.forefire_attempted,
            "forefire_available": context.spread_run.forefire_available,
            "fallback_used": context.spread_run.fallback_used,
            "horizon_minutes": context.spread_run.horizon_minutes,
            "step_minutes": context.spread_run.step_minutes,
            "avg_growth_km2_per_hour": _round(avg_growth),
            "spread_direction_deg": context.spread_run.spread_direction_deg,
            "trusted_point": {
                "longitude": context.trusted_fire_point.longitude,
                "latitude": context.trusted_fire_point.latitude,
                "confidence": context.trusted_fire_point.confidence,
            },
            "environment": {
                "wind_speed_m_s": context.environment_snapshot.wind_speed_m_s,
                "wind_direction_deg": context.environment_snapshot.wind_direction_deg,
                "fire_weather_index": context.environment_snapshot.fire_weather_index,
            },
            "final_step": _step_summary(final_step) if final_step else None,
            "fire_front_steps": [_step_summary(step) for step in steps],
        }

        return agent_result(
            self.agent_name,
            output={
                "spread_packet": spread_packet,
                "spread_summary": spread_summary,
            },
            reasoning=[
                "Built a spread packet from persisted SimulationRun and FireFrontStep records.",
                "This agent currently reads persisted spread results and does not start a new simulation.",
            ],
        )
