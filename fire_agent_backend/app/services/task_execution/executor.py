"""TaskPlan executor for dynamic capability orchestration."""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from app.agents.base import AgentResult, BaseAgent
from app.agents.commander_agent import CommanderAgent
from app.agents.context import AgentAnalysisContext
from app.agents.resource_agent import ResourceAgent
from app.agents.route_agent import RouteAgent
from app.agents.schema import standardize_agent_results
from app.agents.situation_agent import SituationAgent
from app.agents.spread_agent import SpreadAgent
from app.agents.risk_agent import RiskAgent
from app.services.planning import coordinate_route_resource_planning
from app.services.task_execution.models import ExecutionTrace, ExecutionTraceStep, TaskExecutionContext, new_trace_id, utc_now
from app.services.task_planning.models import TaskPlan, TaskStep
from app.services.task_planning.registry import CapabilityRegistry, default_registry


class TaskPlanExecutor:
    """Executes selected TaskPlan capabilities through an explicit whitelist."""

    def __init__(
        self,
        *,
        registry: CapabilityRegistry | None = None,
        agents: Mapping[str, BaseAgent] | None = None,
        commander_agent: CommanderAgent | None = None,
        route_agent: RouteAgent | None = None,
        resource_agent: ResourceAgent | None = None,
    ) -> None:
        self.registry = registry or default_registry()
        self.agents: dict[str, BaseAgent] = {
            "situation_analysis": SituationAgent(),
            "spread_forecast": SpreadAgent(),
            "risk_assessment": RiskAgent(),
            **dict(agents or {}),
        }
        self.commander_agent = commander_agent or CommanderAgent()
        self.route_agent = route_agent or RouteAgent()
        self.resource_agent = resource_agent or ResourceAgent()

    async def execute(self, task_plan: TaskPlan, inputs: TaskExecutionContext) -> dict[str, Any]:
        trace_started = utc_now()
        trace_steps: list[ExecutionTraceStep] = []
        warnings: list[str] = list(task_plan.warnings)
        agent_results: list[AgentResult] = []
        result_map: dict[str, AgentResult] = {}
        capability_status: dict[str, str] = {}
        planning_result: dict[str, Any] | None = None
        route_result: AgentResult | None = None
        resource_result: AgentResult | None = None
        commander_result: AgentResult | None = None

        for step in task_plan.execution_steps:
            self.registry.get(step.capability_id)
            dependency_failures = tuple(
                dependency
                for dependency in step.depends_on
                if capability_status.get(dependency) != "success"
            )
            if step.status == "blocked":
                trace_steps.append(_blocked_trace_step(step, reason=step.blocked_reason or "blocked", missing_inputs=step.missing_inputs))
                capability_status[step.capability_id] = "blocked"
                continue
            if dependency_failures:
                trace_steps.append(_blocked_trace_step(step, reason="blocked_by_dependency", dependency_failures=dependency_failures))
                capability_status[step.capability_id] = "blocked"
                continue
            runtime_missing = _runtime_missing_inputs(step, inputs)
            if runtime_missing:
                trace_steps.append(_blocked_trace_step(step, reason="missing_runtime_inputs", missing_inputs=runtime_missing))
                capability_status[step.capability_id] = "blocked"
                continue

            started_at = utc_now()
            started = time.perf_counter()
            try:
                output = await self._execute_step(step, inputs, result_map, planning_result)
                duration_ms = round((time.perf_counter() - started) * 1000, 3)
                completed_at = utc_now()
                step_warnings: tuple[str, ...] = ()
                result_status = None
                result_ref = None
                if isinstance(output, dict) and output.get("agent_name"):
                    agent_result_output = output  # type: ignore[assignment]
                    agent_results.append(agent_result_output)  # type: ignore[arg-type]
                    result_map[str(agent_result_output["agent_name"])] = agent_result_output  # type: ignore[index]
                    result_status = str(agent_result_output.get("status"))
                    step_warnings = tuple(agent_result_output.get("output", {}).get("warnings") or [])
                    result_ref = str(agent_result_output.get("agent_name"))
                    if step.capability_id == "route_planning":
                        route_result = agent_result_output  # type: ignore[assignment]
                    elif step.capability_id == "resource_dispatch":
                        resource_result = agent_result_output  # type: ignore[assignment]
                    elif step.capability_id == "command_synthesis":
                        commander_result = agent_result_output  # type: ignore[assignment]
                elif step.capability_id == "route_resource_planning":
                    planning_result = output
                    result_status = str(output.get("status"))
                    step_warnings = tuple(output.get("warnings") or [])
                    result_ref = "planning_result"
                    agent_results.extend(_agent_results_from_planning(output))
                    for planning_agent_result in _agent_results_from_planning(output):
                        result_map[str(planning_agent_result["agent_name"])] = planning_agent_result
                success = result_status == "success"
                capability_status[step.capability_id] = "success" if success else "failed"
                trace_steps.append(
                    ExecutionTraceStep(
                        step_id=step.step_id,
                        capability_id=step.capability_id,
                        provider=step.provider,
                        status="success" if success else "failed",
                        depends_on=step.depends_on,
                        started_at=started_at,
                        completed_at=completed_at,
                        duration_ms=duration_ms,
                        input_status="ready",
                        result_status=result_status,
                        warnings=step_warnings,
                        diagnostics={"result_ref": result_ref},
                        result_ref=result_ref,
                    )
                )
            except Exception as exc:
                duration_ms = round((time.perf_counter() - started) * 1000, 3)
                capability_status[step.capability_id] = "failed"
                trace_steps.append(
                    ExecutionTraceStep(
                        step_id=step.step_id,
                        capability_id=step.capability_id,
                        provider=step.provider,
                        status="failed",
                        depends_on=step.depends_on,
                        started_at=started_at,
                        completed_at=utc_now(),
                        duration_ms=duration_ms,
                        input_status="ready",
                        result_status="error",
                        warnings=(str(exc),),
                        diagnostics={"error": str(exc)},
                        result_ref=None,
                    )
                )
                warnings.append(f"{step.capability_id} failed: {exc}")

        analysis_context = AgentAnalysisContext.from_agent_results(result_map)
        status = _overall_status(trace_steps)
        completed_at = utc_now()
        trace = ExecutionTrace(
            trace_id=new_trace_id(),
            task_plan_id=str(task_plan.metadata.get("task_plan_id")) if task_plan.metadata.get("task_plan_id") else None,
            status=status,
            started_at=trace_started,
            completed_at=completed_at,
            steps=tuple(trace_steps),
            warnings=tuple(_ordered_unique(warnings)),
            diagnostics={
                "selected_capabilities": list(task_plan.selected_capabilities),
                "executed_agent_count": len(agent_results),
                "synthetic_defaults_used": False,
            },
        )
        return {
            "task_plan": task_plan.to_dict(),
            "overall_status": status,
            "agent_results": agent_results,
            "analysis_context": analysis_context.to_dict(),
            "commander_result": commander_result,
            "planning_result": planning_result,
            "route_result": route_result,
            "resource_result": resource_result,
            "standard_outputs": standardize_agent_results(agent_results),
            "execution_trace": trace.to_dict(),
        }

    async def _execute_step(
        self,
        step: TaskStep,
        inputs: TaskExecutionContext,
        result_map: Mapping[str, AgentResult],
        planning_result: Mapping[str, Any] | None,
    ) -> Any:
        if step.capability_id == "situation_analysis":
            return self.agents["situation_analysis"].run(inputs.decision_context, result_map)  # type: ignore[arg-type]
        if step.capability_id == "spread_forecast":
            return self.agents["spread_forecast"].run(inputs.decision_context, result_map)  # type: ignore[arg-type]
        if step.capability_id == "risk_assessment":
            return self.agents["risk_assessment"].run(inputs.decision_context, result_map)  # type: ignore[arg-type]
        if step.capability_id == "route_planning":
            return self.route_agent.run(inputs.route_task)  # type: ignore[arg-type]
        if step.capability_id == "resource_dispatch":
            return self.resource_agent.run(inputs.resource_task)  # type: ignore[arg-type]
        if step.capability_id == "route_resource_planning":
            return coordinate_route_resource_planning(inputs.planning_task).to_dict()  # type: ignore[arg-type]
        if step.capability_id == "command_synthesis":
            analysis_context = AgentAnalysisContext.from_agent_results(result_map)
            return await self.commander_agent.run(
                analysis_context,
                planning_result=planning_result,
                force_provider=inputs.force_provider,
            )
        raise ValueError(f"No executor is registered for capability: {step.capability_id}")


def _runtime_missing_inputs(step: TaskStep, inputs: TaskExecutionContext) -> tuple[str, ...]:
    if step.capability_id in {"situation_analysis", "spread_forecast", "risk_assessment", "command_synthesis"}:
        return () if inputs.decision_context is not None else ("decision_context",)
    if step.capability_id == "route_planning":
        return () if inputs.route_task is not None else ("route_task",)
    if step.capability_id == "resource_dispatch":
        return () if inputs.resource_task is not None else ("resource_task",)
    if step.capability_id == "route_resource_planning":
        return () if inputs.planning_task is not None else ("planning_task",)
    return tuple(item for item in step.required_inputs if not inputs.input_available(item))


def _blocked_trace_step(
    step: TaskStep,
    *,
    reason: str,
    missing_inputs: tuple[str, ...] = (),
    dependency_failures: tuple[str, ...] = (),
) -> ExecutionTraceStep:
    diagnostics: dict[str, Any] = {"reason": reason}
    if dependency_failures:
        diagnostics["blocked_by"] = list(dependency_failures)
    return ExecutionTraceStep(
        step_id=step.step_id,
        capability_id=step.capability_id,
        provider=step.provider,
        status="blocked",
        depends_on=step.depends_on,
        input_status="missing" if missing_inputs else "dependency_blocked",
        missing_inputs=missing_inputs,
        result_status="blocked",
        warnings=(reason,),
        diagnostics=diagnostics,
    )


def _agent_results_from_planning(planning_result: Mapping[str, Any]) -> list[AgentResult]:
    results: list[AgentResult] = []
    resource_result = planning_result.get("resource_agent_result")
    if isinstance(resource_result, dict) and resource_result.get("agent_name"):
        results.append(resource_result)  # type: ignore[arg-type]
    route_results = planning_result.get("route_agent_results") or {}
    if isinstance(route_results, Mapping):
        for route_result in route_results.values():
            if isinstance(route_result, dict) and route_result.get("agent_name"):
                results.append(route_result)  # type: ignore[arg-type]
    return results


def _overall_status(steps: list[ExecutionTraceStep]) -> str:
    if not steps:
        return "blocked"
    statuses = [step.status for step in steps]
    if all(status == "success" for status in statuses):
        return "success"
    if any(status == "success" for status in statuses):
        return "partial"
    if any(status == "failed" for status in statuses):
        return "failed"
    return "blocked"


def _ordered_unique(values):
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return tuple(result)
