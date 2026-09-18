"""Models for the natural-language command pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from app.agents.context import DecisionContext
from app.agents.resource_agent import ResourceAgentTask
from app.agents.route_agent import RouteTask
from app.services.planning import PlanningTask
from app.services.task_execution import TaskExecutionContext
from app.services.task_planning import NaturalLanguageTaskRequest

CommandStatus = Literal["success", "partial", "blocked", "failed"]


@dataclass(frozen=True)
class CommandRequest:
    """High-level natural-language command request.

    The request carries actual typed inputs. The pipeline derives planner
    availability from these inputs instead of accepting caller-built flags.
    """

    user_query: str
    decision_context: DecisionContext | None = None
    planning_task: PlanningTask | None = None
    route_task: RouteTask | None = None
    resource_task: ResourceAgentTask | None = None
    language: str = "zh"
    force_provider: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def derive_available_inputs(self) -> dict[str, bool]:
        available: dict[str, bool] = {
            "decision_context": self.decision_context is not None,
            "planning_task": self.planning_task is not None,
            "route_task": self.route_task is not None,
            "resource_task": self.resource_task is not None,
        }
        if self.route_task is not None:
            available.update(
                {
                    "road_network": True,
                    "start": True,
                    "destination": True,
                }
            )
        if self.resource_task is not None:
            available.update(
                {
                    "road_network": True,
                    "resource_inventory": True,
                    "target": True,
                }
            )
        if self.planning_task is not None:
            available.update(
                {
                    "road_network": True,
                    "resource_inventory": True,
                    "target": True,
                }
            )
        return available

    def to_task_request(self) -> NaturalLanguageTaskRequest:
        return NaturalLanguageTaskRequest(
            query=self.user_query,
            language=self.language,
            available_inputs=self.derive_available_inputs(),
            metadata={
                **dict(self.metadata),
                "pipeline": "NaturalLanguageCommandPipeline",
                "available_inputs_derived": True,
                "synthetic_defaults_used": False,
            },
        )

    def to_execution_context(self) -> TaskExecutionContext:
        return TaskExecutionContext(
            decision_context=self.decision_context,
            planning_task=self.planning_task,
            route_task=self.route_task,
            resource_task=self.resource_task,
            force_provider=self.force_provider,
            metadata={
                **dict(self.metadata),
                "available_inputs": self.derive_available_inputs(),
                "synthetic_defaults_used": False,
            },
        )


@dataclass(frozen=True)
class CommandResult:
    query: str
    status: CommandStatus
    task_plan: Mapping[str, Any]
    execution_trace: Mapping[str, Any]
    agent_results: tuple[Mapping[str, Any], ...] = ()
    standard_outputs: tuple[Mapping[str, Any], ...] = ()
    analysis_context: Mapping[str, Any] = field(default_factory=dict)
    planning_result: Mapping[str, Any] | None = None
    commander_result: Mapping[str, Any] | None = None
    missing_inputs: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "status": self.status,
            "task_plan": dict(self.task_plan),
            "execution_trace": dict(self.execution_trace),
            "agent_results": [dict(item) for item in self.agent_results],
            "standard_outputs": [dict(item) for item in self.standard_outputs],
            "analysis_context": dict(self.analysis_context),
            "planning_result": dict(self.planning_result) if self.planning_result is not None else None,
            "commander_result": dict(self.commander_result) if self.commander_result is not None else None,
            "missing_inputs": list(self.missing_inputs),
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }
