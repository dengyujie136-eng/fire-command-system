"""Models for the standalone wildfire resource dispatch calculation unit."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.services.routing import VehicleProfile

ResourceType = Literal[
    "fire_team",
    "fire_engine",
    "firefighter_unit",
    "uav",
    "water_supply",
    "medical",
    "evacuation_support",
    "ground_vehicle",
]
ResourceStatus = Literal["available", "assigned", "unavailable", "maintenance", "blocked", "unreachable"]
MobilityMode = Literal["ground", "air", "static"]
TaskType = Literal["fire_suppression", "structure_protection", "reconnaissance", "evacuation_support"]
DispatchStrategy = Literal["fastest_response", "safest_response", "capability_first", "balanced"]
EvaluationStatus = Literal["candidate", "selected", "rejected"]


@dataclass(frozen=True)
class Resource:
    resource_id: str
    resource_type: ResourceType
    name: str
    location_node_id: str | None = None
    longitude: float | None = None
    latitude: float | None = None
    status: ResourceStatus = "available"
    available: bool = True
    capabilities: frozenset[str] = field(default_factory=frozenset)
    capacity: dict[str, float] = field(default_factory=dict)
    quantity: int = 1
    readiness: float = 1.0
    mobility_mode: MobilityMode = "ground"
    vehicle_profile: VehicleProfile | None = None
    response_speed_kmh: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_available(self) -> bool:
        return self.available and self.status == "available" and self.quantity > 0 and self.readiness > 0

    def to_summary(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "name": self.name,
            "location_node_id": self.location_node_id,
            "longitude": self.longitude,
            "latitude": self.latitude,
            "status": self.status,
            "available": self.available,
            "capabilities": sorted(self.capabilities),
            "capacity": dict(self.capacity),
            "quantity": self.quantity,
            "readiness": round(float(self.readiness), 3),
            "mobility_mode": self.mobility_mode,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ResourceRequirement:
    resource_type: ResourceType
    quantity: int = 1
    required_capabilities: frozenset[str] = field(default_factory=frozenset)
    minimum_capacity: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ResourceTask:
    task_id: str
    task_type: TaskType
    target_node_id: str
    priority: str = "high"
    required_capabilities: frozenset[str] = field(default_factory=frozenset)
    minimum_resource_requirements: tuple[ResourceRequirement, ...] = field(default_factory=tuple)
    desired_resource_requirements: tuple[ResourceRequirement, ...] = field(default_factory=tuple)
    strategy: DispatchStrategy = "balanced"
    deadline_minutes: float | None = None
    route_risk_weight: float = 20.0
    blocked_edge_ids: frozenset[str] = field(default_factory=frozenset)
    edge_status_overrides: dict[str, str] = field(default_factory=dict)
    edge_risk_overrides: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResourceDispatchResult:
    success: bool
    status: Literal["success", "partial", "failed"]
    task: dict[str, Any]
    strategy: DispatchStrategy
    selected_resources: list[dict[str, Any]]
    candidate_resources: list[dict[str, Any]]
    rejected_resources: list[dict[str, Any]]
    resource_shortage: list[dict[str, Any]]
    total_resource_count: int
    estimated_response: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "status": self.status,
            "task": dict(self.task),
            "strategy": self.strategy,
            "selected_resources": list(self.selected_resources),
            "candidate_resources": list(self.candidate_resources),
            "rejected_resources": list(self.rejected_resources),
            "resource_shortage": list(self.resource_shortage),
            "total_resource_count": self.total_resource_count,
            "estimated_response": dict(self.estimated_response),
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }