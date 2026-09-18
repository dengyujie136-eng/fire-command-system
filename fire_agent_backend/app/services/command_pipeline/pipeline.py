"""Natural-language command pipeline connecting planner and executor."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.services.command_pipeline.models import CommandRequest, CommandResult, CommandStatus
from app.services.task_execution import TaskPlanExecutor
from app.services.task_planning import NaturalLanguageTaskPlanner


class NaturalLanguageCommandPipeline:
    """Thin internal entrypoint for user query -> TaskPlan -> execution."""

    def __init__(
        self,
        *,
        planner: NaturalLanguageTaskPlanner | None = None,
        executor: TaskPlanExecutor | None = None,
        llm_provider: Any | None = None,
    ) -> None:
        self.planner = planner or NaturalLanguageTaskPlanner(llm_provider=llm_provider)
        self.executor = executor or TaskPlanExecutor()

    async def run(self, request: CommandRequest) -> CommandResult:
        task_request = request.to_task_request()
        task_plan = await self.planner.plan(task_request, force_provider=request.force_provider)
        execution = await self.executor.execute(task_plan, request.to_execution_context())
        task_plan_dict = execution.get("task_plan") or task_plan.to_dict()
        trace = execution.get("execution_trace") or {}
        status = _coerce_status(str(execution.get("overall_status") or trace.get("status") or "failed"))

        missing_inputs = _ordered_unique(
            [
                *task_plan.missing_inputs,
                *_missing_inputs_from_trace(trace),
            ]
        )
        warnings = _ordered_unique(
            [
                *task_plan.warnings,
                *(trace.get("warnings") or []),
            ]
        )

        return CommandResult(
            query=request.user_query,
            status=status,
            task_plan=task_plan_dict,
            execution_trace=trace,
            agent_results=tuple(execution.get("agent_results") or ()),
            standard_outputs=tuple(execution.get("standard_outputs") or ()),
            analysis_context=execution.get("analysis_context") or {},
            planning_result=execution.get("planning_result"),
            commander_result=execution.get("commander_result"),
            missing_inputs=missing_inputs,
            warnings=warnings,
            metadata={
                **dict(request.metadata),
                "pipeline": "NaturalLanguageCommandPipeline",
                "available_inputs": request.derive_available_inputs(),
                "available_inputs_derived": True,
                "planner_source": task_plan.planner_source,
                "fallback_used": task_plan.fallback_used,
                "force_provider": request.force_provider,
                "synthetic_defaults_used": False,
            },
        )


def _coerce_status(status: str) -> CommandStatus:
    if status in {"success", "partial", "blocked", "failed"}:
        return status  # type: ignore[return-value]
    return "failed"


def _missing_inputs_from_trace(trace: Mapping[str, Any]) -> tuple[str, ...]:
    missing: list[str] = []
    for step in trace.get("steps") or []:
        if isinstance(step, Mapping):
            missing.extend(str(item) for item in step.get("missing_inputs") or [])
    return tuple(missing)


def _ordered_unique(values: Iterable[Any]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        value = str(value)
        if value and value not in result:
            result.append(value)
    return tuple(result)
