"""Execution models for TaskPlan-driven orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Mapping
from uuid import uuid4

from app.agents.context import DecisionContext
from app.agents.route_agent import RouteTask
from app.agents.resource_agent import ResourceAgentTask
from app.services.planning import PlanningTask

TraceStepStatus = Literal["pending", "running", "success", "failed", "blocked", "skipped"]
ExecutionStatus = Literal["success", "partial", "failed", "blocked"]


@dataclass(slots=True)
class TaskExecutionContext:
    """Structured inputs available to a TaskPlanExecutor run."""

    decision_context: DecisionContext | None = None
    planning_task: PlanningTask | None = None
    route_task: RouteTask | None = None
    resource_task: ResourceAgentTask | None = None
    force_provider: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def input_available(self, input_name: str) -> bool:
        if input_name == "decision_context":
            return self.decision_context is not None
        if input_name == "planning_task":
            return self.planning_task is not None
        if input_name in {"road_network", "resource_inventory", "target"}:
            return self.planning_task is not None or self.resource_task is not None or self.route_task is not None
        if input_name in {"start", "destination"}:
            return self.route_task is not None
        if input_name == "planning_result":
            return False
        return bool(self.metadata.get("available_inputs", {}).get(input_name))


@dataclass(frozen=True)
class ExecutionTraceStep:
    step_id: str
    capability_id: str
    provider: str
    status: TraceStepStatus
    depends_on: tuple[str, ...] = ()
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: float | None = None
    input_status: str = "ready"
    missing_inputs: tuple[str, ...] = ()
    result_status: str | None = None
    warnings: tuple[str, ...] = ()
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    result_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "capability_id": self.capability_id,
            "provider": self.provider,
            "status": self.status,
            "depends_on": list(self.depends_on),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "input_status": self.input_status,
            "missing_inputs": list(self.missing_inputs),
            "result_status": self.result_status,
            "warnings": list(self.warnings),
            "diagnostics": dict(self.diagnostics),
            "result_ref": self.result_ref,
        }


@dataclass(frozen=True)
class ExecutionTrace:
    trace_id: str
    task_plan_id: str | None
    status: ExecutionStatus
    started_at: str
    completed_at: str
    steps: tuple[ExecutionTraceStep, ...]
    warnings: tuple[str, ...] = ()
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "task_plan_id": self.task_plan_id,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "steps": [step.to_dict() for step in self.steps],
            "warnings": list(self.warnings),
            "diagnostics": dict(self.diagnostics),
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_trace_id() -> str:
    return f"trace_{uuid4().hex[:18]}"
