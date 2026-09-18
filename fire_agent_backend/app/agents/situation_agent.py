"""Rule-based situation analysis agent."""

from __future__ import annotations

from typing import Mapping

from app.agents.base import AgentResult, BaseAgent, agent_result
from app.agents.context import AgentContext
from app.integrations.schemas import IncidentContext


class SituationAgent(BaseAgent):
    agent_name = "SituationAgent"

    def run(
        self,
        context: AgentContext,
        prior_results: Mapping[str, AgentResult] | None = None,
    ) -> AgentResult:
        if isinstance(context, IncidentContext):
            weather = context.weather[0] if context.weather else None
            environment_packet = weather.model_dump() if weather else {}
            trusted_point_packet = {
                'longitude': context.ignition.longitude,
                'latitude': context.ignition.latitude,
                'confidence': context.ignition.confidence,
                'confirmation_id': context.ignition.confirmation_id,
                'source_candidate_id': context.ignition.source_candidate_id,
            }
            situation_packet = {
                'summary': (
                    f'{context.event.name}: visual confirmation '
                    f'{context.ignition.confirmation_id} accepted with confidence '
                    f'{context.ignition.confidence:.2f}.'
                ),
                'trusted_point': trusted_point_packet,
                'environment': environment_packet,
                'visual_status': context.candidate.visual_status,
            }
            situation_summary = {
                'event': context.event.model_dump(mode='json'),
                'candidate': context.candidate.model_dump(mode='json'),
                'confirmed_fire_point': context.ignition.model_dump(mode='json'),
                'visual_findings': context.visual_findings,
                'environment': environment_packet,
                'data_sources': [
                    'member_a_candidate_and_weather',
                    'member_b_visual_confirmation',
                ],
            }
            return agent_result(
                self.agent_name,
                output={
                    'situation_packet': situation_packet,
                    'situation_summary': situation_summary,
                },
                reasoning=[
                    'Summarized member A observations and member B confirmed evidence.',
                    'No visual recognition, data acquisition, or spread calculation is performed here.',
                ],
            )

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
