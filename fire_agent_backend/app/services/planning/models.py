"""Internal planning models for route-resource coordination."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Sequence

from app.services.resources import Resource, ResourceRequirement, ResourceTask
from app.services.resources.models import DispatchStrategy, TaskType
from app.services.routing import RoadNetwork

PlanningRouteObjective = Literal["shortest", "fastest", "safest", "compare"]
OperationalRouteSource = Literal["dispatch_route", "route_preference"]


@dataclass(frozen=True)
class PlanningTask:
    """Internal input for RouteAgent + ResourceAgent coordination."""

    task_id: str
    task_type: TaskType
    target_node_id: str
    resource_inventory: Sequence[Resource]
    road_network: RoadNetwork
    resource_strategy: DispatchStrategy = "balanced"
    route_objective: PlanningRouteObjective = "compare"
    operational_route_source: OperationalRouteSource = "dispatch_route"
    priority: str = "high"
    incident_id: str | None = None
    protection_target: str | None = None
    deadline_minutes: float | None = None
    scenario_version: str | None = None
    required_capabilities: frozenset[str] = field(default_factory=frozenset)
    minimum_resource_requirements: tuple[ResourceRequirement, ...] = field(default_factory=tuple)
    desired_resource_requirements: tuple[ResourceRequirement, ...] = field(default_factory=tuple)
    route_risk_weight: float = 20.0
    blocked_edge_ids: frozenset[str] = field(default_factory=frozenset)
    edge_status_overrides: dict[str, str] = field(default_factory=dict)
    edge_risk_overrides: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_resource_task(self) -> ResourceTask:
        return ResourceTask(
            task_id=self.task_id,
            task_type=self.task_type,
            target_node_id=self.target_node_id,
            priority=self.priority,
            required_capabilities=self.required_capabilities,
            minimum_resource_requirements=self.minimum_resource_requirements,
            desired_resource_requirements=self.desired_resource_requirements,
            strategy=self.resource_strategy,
            deadline_minutes=self.deadline_minutes,
            route_risk_weight=self.route_risk_weight,
            blocked_edge_ids=self.blocked_edge_ids,
            edge_status_overrides=self.edge_status_overrides,
            edge_risk_overrides=self.edge_risk_overrides,
            metadata={
                **self.metadata,
                "incident_id": self.incident_id,
                "protection_target": self.protection_target,
                "scenario_version": self.scenario_version,
            },
        )


@dataclass(frozen=True)
class PlanningResult:
    success: bool
    status: str
    task: dict[str, Any]
    resource_result: dict[str, Any]
    route_results: list[dict[str, Any]]
    route_agent_results: dict[str, dict[str, Any]]
    resource_agent_result: dict[str, Any]
    selected_resources: list[dict[str, Any]]
    operational_routes: list[dict[str, Any]]
    alternative_routes: list[dict[str, Any]]
    rejected_resources: list[dict[str, Any]]
    resource_shortage: list[dict[str, Any]]
    estimated_response: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "status": self.status,
            "task": dict(self.task),
            "resource_result": dict(self.resource_result),
            "route_results": list(self.route_results),
            "route_agent_results": dict(self.route_agent_results),
            "resource_agent_result": dict(self.resource_agent_result),
            "selected_resources": list(self.selected_resources),
            "operational_routes": list(self.operational_routes),
            "alternative_routes": list(self.alternative_routes),
            "rejected_resources": list(self.rejected_resources),
            "resource_shortage": list(self.resource_shortage),
            "estimated_response": dict(self.estimated_response),
            "warnings": list(self.warnings),
            "diagnostics": dict(self.diagnostics),
            "metadata": dict(self.metadata),
        }
