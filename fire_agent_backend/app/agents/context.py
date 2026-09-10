"""Context object passed through the decision agent pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from app.models.event import FireEvent
from app.models.observation import FusionResult, TrustedFirePoint
from app.models.scenario import EnvironmentSnapshot
from app.models.spread import FireFrontStep, SimulationRun


@dataclass(slots=True)
class DecisionContext:
    event: FireEvent
    trusted_fire_point: TrustedFirePoint
    environment_snapshot: EnvironmentSnapshot
    fusion_result: FusionResult | None
    spread_run: SimulationRun
    fire_front_steps: list[FireFrontStep]

    @property
    def event_id(self) -> str:
        return self.event.event_id

    @property
    def scenario_id(self) -> str | None:
        return self.environment_snapshot.scenario_id


@dataclass(slots=True)
class AgentAnalysisContext:
    situation: dict[str, Any] = field(default_factory=dict)
    spread: dict[str, Any] = field(default_factory=dict)
    risk: dict[str, Any] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def from_agent_results(cls, results: Mapping[str, Mapping[str, Any]]) -> "AgentAnalysisContext":
        situation_output = results.get("SituationAgent", {}).get("output", {})
        spread_output = results.get("SpreadAgent", {}).get("output", {})
        risk_output = results.get("RiskAgent", {}).get("output", {})

        return cls(
            situation={
                "situation_packet": situation_output.get("situation_packet", {}),
                "situation_summary": situation_output.get("situation_summary", {}),
            },
            spread={
                "spread_packet": spread_output.get("spread_packet", {}),
                "spread_summary": spread_output.get("spread_summary", {}),
            },
            risk={
                "risk_packet": risk_output.get("risk_packet", {}),
                "risk_summary": risk_output.get("risk_summary", {}),
                "risk_level": risk_output.get("risk_level"),
                "risk_factors": risk_output.get("risk_factors", []),
                "warnings": risk_output.get("warnings", []),
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "situation": self.situation,
            "spread": self.spread,
            "risk": self.risk,
            "generated_at": self.generated_at,
        }
