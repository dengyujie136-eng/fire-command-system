"""Whitelist registry for currently implemented planning capabilities."""

from __future__ import annotations

from typing import Iterable

from app.services.task_planning.models import CapabilityDefinition


class CapabilityRegistry:
    """Small static whitelist of project capabilities available to Task Planner."""

    def __init__(self, capabilities: Iterable[CapabilityDefinition] | None = None) -> None:
        self._capabilities = {item.capability_id: item for item in (capabilities or _default_capabilities())}

    def get(self, capability_id: str) -> CapabilityDefinition:
        try:
            return self._capabilities[capability_id]
        except KeyError as exc:
            raise ValueError(f"Unknown capability: {capability_id}") from exc

    def has(self, capability_id: str) -> bool:
        return capability_id in self._capabilities

    def all(self) -> tuple[CapabilityDefinition, ...]:
        return tuple(self._capabilities.values())

    def selectable_ids(self) -> tuple[str, ...]:
        return tuple(item.capability_id for item in self._capabilities.values() if item.selectable)

    def validate(self, capability_ids: Iterable[str]) -> tuple[str, ...]:
        valid: list[str] = []
        for capability_id in capability_ids:
            capability = self.get(str(capability_id))
            if not capability.selectable:
                raise ValueError(f"Capability is not selectable: {capability_id}")
            if capability.capability_id not in valid:
                valid.append(capability.capability_id)
        return tuple(valid)

    def apply_subsumption(self, capability_ids: Iterable[str]) -> tuple[str, ...]:
        ordered = list(self.validate(capability_ids))
        subsumed: set[str] = set()
        for capability_id in ordered:
            subsumed.update(self.get(capability_id).subsumes)
        return tuple(capability_id for capability_id in ordered if capability_id not in subsumed)

    def to_dict(self) -> dict[str, dict]:
        return {item.capability_id: item.to_dict() for item in self._capabilities.values()}


def default_registry() -> CapabilityRegistry:
    return CapabilityRegistry()


def _default_capabilities() -> tuple[CapabilityDefinition, ...]:
    return (
        CapabilityDefinition(
            capability_id="situation_analysis",
            name="Situation Analysis",
            description="Analyze current wildfire situation from DecisionContext.",
            provider="SituationAgent",
            required_inputs=("decision_context",),
            output_type="situation_packet",
            execution_role="analysis",
        ),
        CapabilityDefinition(
            capability_id="spread_forecast",
            name="Spread Forecast",
            description="Forecast wildfire spread from existing spread run and fire front steps.",
            provider="SpreadAgent",
            required_inputs=("decision_context",),
            dependencies=("situation_analysis",),
            output_type="spread_packet",
            execution_role="analysis",
        ),
        CapabilityDefinition(
            capability_id="risk_assessment",
            name="Risk Assessment",
            description="Assess wildfire risk from situation and spread outputs.",
            provider="RiskAgent",
            required_inputs=("decision_context",),
            dependencies=("situation_analysis", "spread_forecast"),
            output_type="risk_packet",
            execution_role="analysis",
        ),
        CapabilityDefinition(
            capability_id="route_planning",
            name="Route Planning",
            description="Plan a route with RouteAgent and Routing Unit when road inputs are supplied.",
            provider="RouteAgent + Routing Unit",
            required_inputs=("road_network", "start", "destination"),
            optional_inputs=("blocked_edges", "edge_risk_overrides", "route_preference"),
            output_type="route_agent_result",
            execution_role="professional_calculation",
        ),
        CapabilityDefinition(
            capability_id="resource_dispatch",
            name="Resource Dispatch",
            description="Select dispatch resources with ResourceAgent and Resource Calculation Unit.",
            provider="ResourceAgent + Resource Calculation Unit",
            required_inputs=("resource_inventory", "target", "road_network"),
            optional_inputs=("resource_requirements", "blocked_edges", "edge_risk_overrides"),
            output_type="resource_agent_result",
            execution_role="professional_calculation",
        ),
        CapabilityDefinition(
            capability_id="route_resource_planning",
            name="Route-Resource Planning",
            description="Coordinate route and resource planning through the Planning Service.",
            provider="Planning Service",
            required_inputs=("planning_task", "road_network", "resource_inventory", "target"),
            optional_inputs=("blocked_edges", "edge_risk_overrides", "route_preference"),
            subsumes=("route_planning", "resource_dispatch"),
            output_type="planning_result",
            execution_role="coordination",
        ),
        CapabilityDefinition(
            capability_id="command_synthesis",
            name="Command Synthesis",
            description="Synthesize command-facing recommendations from completed professional outputs.",
            provider="CommanderAgent",
            required_inputs=("decision_context",),
            dependencies=("situation_analysis",),
            optional_inputs=("planning_result",),
            output_type="commander_result",
            execution_role="synthesis",
            execution_type="llm_assisted_summary",
            deterministic=False,
            llm_assisted=True,
        ),
    )
