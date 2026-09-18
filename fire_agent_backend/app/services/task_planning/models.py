"""Internal models for natural-language task planning."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

CapabilityId = Literal[
    "situation_analysis",
    "spread_forecast",
    "risk_assessment",
    "route_planning",
    "resource_dispatch",
    "route_resource_planning",
    "command_synthesis",
]
PlannerSource = Literal["deterministic", "llm", "llm_fallback"]
StepStatus = Literal["ready", "blocked"]
PlanStatus = Literal["ready", "partial", "blocked"]


@dataclass(frozen=True)
class CapabilityDefinition:
    capability_id: str
    name: str
    description: str
    provider: str
    required_inputs: tuple[str, ...] = ()
    optional_inputs: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    subsumes: tuple[str, ...] = ()
    output_type: str = "structured"
    execution_role: str = "planning_only"
    execution_type: str = "deterministic"
    deterministic: bool = True
    llm_assisted: bool = False
    availability: str = "available"
    selectable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "description": self.description,
            "provider": self.provider,
            "required_inputs": list(self.required_inputs),
            "optional_inputs": list(self.optional_inputs),
            "dependencies": list(self.dependencies),
            "subsumes": list(self.subsumes),
            "output_type": self.output_type,
            "execution_role": self.execution_role,
            "execution_type": self.execution_type,
            "deterministic": self.deterministic,
            "llm_assisted": self.llm_assisted,
            "availability": self.availability,
            "selectable": self.selectable,
        }


@dataclass(frozen=True)
class NaturalLanguageTaskRequest:
    query: str
    language: str = "zh"
    available_inputs: Mapping[str, bool] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def has_input(self, input_name: str) -> bool:
        return bool(self.available_inputs.get(input_name))


@dataclass(frozen=True)
class TaskStep:
    step_id: str
    capability_id: str
    name: str
    provider: str
    depends_on: tuple[str, ...] = ()
    required_inputs: tuple[str, ...] = ()
    missing_inputs: tuple[str, ...] = ()
    status: StepStatus = "ready"
    blocked_reason: str | None = None
    execution_role: str = "planning_only"

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "capability_id": self.capability_id,
            "name": self.name,
            "provider": self.provider,
            "depends_on": list(self.depends_on),
            "required_inputs": list(self.required_inputs),
            "missing_inputs": list(self.missing_inputs),
            "status": self.status,
            "blocked_reason": self.blocked_reason,
            "execution_role": self.execution_role,
        }


@dataclass(frozen=True)
class TaskPlan:
    original_query: str
    intent: str
    requested_outputs: tuple[str, ...]
    selected_capabilities: tuple[str, ...]
    execution_steps: tuple[TaskStep, ...]
    dependencies: Mapping[str, tuple[str, ...]]
    required_inputs: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    executable: bool
    status: PlanStatus
    warnings: tuple[str, ...]
    planner_source: PlannerSource
    metadata: Mapping[str, Any] = field(default_factory=dict)
    capability_reasons: Mapping[str, str] = field(default_factory=dict)
    blocked_steps: tuple[str, ...] = ()
    fallback_used: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_query": self.original_query,
            "intent": self.intent,
            "requested_outputs": list(self.requested_outputs),
            "selected_capabilities": list(self.selected_capabilities),
            "execution_steps": [step.to_dict() for step in self.execution_steps],
            "dependencies": {key: list(value) for key, value in self.dependencies.items()},
            "required_inputs": list(self.required_inputs),
            "missing_inputs": list(self.missing_inputs),
            "executable": self.executable,
            "status": self.status,
            "warnings": list(self.warnings),
            "planner_source": self.planner_source,
            "metadata": dict(self.metadata),
            "capability_reasons": dict(self.capability_reasons),
            "blocked_steps": list(self.blocked_steps),
            "fallback_used": self.fallback_used,
        }
