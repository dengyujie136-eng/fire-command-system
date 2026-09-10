"""Rule-based situation analysis agent."""

from __future__ import annotations

from typing import Mapping

from app.agents.base import AgentResult, BaseAgent, agent_result
from app.agents.context import DecisionContext


class SituationAgent(BaseAgent):
    agent_name = "SituationAgent"

    def run(
        self,
        context: DecisionContext,
        prior_results: Mapping[str, AgentResult] | None = None,
    ) -> AgentResult:
        trusted_point = context.trusted_fire_point
        environment = context.environment_snapshot
        fusion = context.fusion_result
        fusion_confidence = fusion.confidence if fusion else trusted_point.confidence
        trusted_point_packet = {
            "longitude": trusted_point.longitude,
            "latitude": trusted_point.latitude,
            "confidence": trusted_point.confidence,
        }
        environment_packet = {
            "temperature_c": environment.temperature_c,
            "humidity_percent": environment.humidity_percent,
            "wind_speed_m_s": environment.wind_speed_m_s,
            "wind_direction_deg": environment.wind_direction_deg,
            "fire_weather_index": environment.fire_weather_index,
        }
        situation_packet = {
            "summary": f"{context.event.name}: trusted fire point confirmed with confidence {fusion_confidence:.2f}.",
            "trusted_point": trusted_point_packet,
            "environment": environment_packet,
        }

        situation_summary = {
            "event": {
                "event_id": context.event.event_id,
                "name": context.event.name,
                "status": context.event.status,
                "started_at": context.event.started_at.isoformat()
                if context.event.started_at
                else None,
            },
            "trusted_fire_point": {
                **trusted_point_packet,
                "level": trusted_point.level,
            },
            "environment": environment_packet,
            "fusion": {
                "fusion_id": fusion.fusion_id,
                "confidence": fusion.confidence,
                "evidence_count": fusion.evidence_count,
                "evidence_sources": fusion.evidence_sources,
                "decision": fusion.decision,
            }
            if fusion
            else None,
        }

        return agent_result(
            self.agent_name,
            output={
                "situation_packet": situation_packet,
                "situation_summary": situation_summary,
            },
            reasoning=[
                "Built a situation packet compatible with the legacy decision_service output.",
                "No LLM call is used in the first-stage rule-based framework.",
            ],
        )
