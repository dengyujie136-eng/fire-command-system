"""Sequential orchestrator for the decision agent pipeline."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Mapping

from app.agents.base import AgentResult, BaseAgent, agent_result
from app.agents.commander_agent import CommanderAgent
from app.agents.context import AgentAnalysisContext, DecisionContext
from app.agents.risk_agent import RiskAgent
from app.agents.schema import standardize_agent_results
from app.agents.situation_agent import SituationAgent
from app.agents.spread_agent import SpreadAgent
from app.services.planning import PlanningTask, coordinate_route_resource_planning
from app.services.task_execution import TaskExecutionContext, TaskPlanExecutor
from app.services.task_planning import TaskPlan


class MultiAgentOrchestrator:
    """Runs analysis agents and builds a command-ready context."""

    def __init__(
        self,
        agents: Sequence[BaseAgent] | None = None,
        commander_agent: CommanderAgent | None = None,
    ) -> None:
        self.agents = list(
            agents
            or [
                SituationAgent(),
                SpreadAgent(),
                RiskAgent(),
            ]
        )
        self.commander_agent = commander_agent or CommanderAgent()

    async def run(
        self,
        context: DecisionContext | None,
        force_provider: str | None = None,
        planning_task: PlanningTask | None = None,
        task_plan: TaskPlan | None = None,
        execution_inputs: TaskExecutionContext | None = None,
    ) -> dict[str, Any]:
        if task_plan is not None:
            executor_inputs = execution_inputs or TaskExecutionContext(
                decision_context=context,
                planning_task=planning_task,
                force_provider=force_provider,
            )
            executor = TaskPlanExecutor(
                agents=_capability_agents(self.agents),
                commander_agent=self.commander_agent,
            )
            return await executor.execute(task_plan, executor_inputs)
        if context is None:
            raise ValueError("DecisionContext is required when task_plan is not provided.")

        result_map: dict[str, AgentResult] = {}
        agent_results: list[AgentResult] = []

        for agent in self.agents:
            try:
                result = agent.run(context, result_map)
            except Exception as exc:
                result = agent_result(
                    agent.agent_name,
                    status="error",
                    output={"error": str(exc)},
                    reasoning=["Agent execution failed before producing a valid output."],
                )
            result_map[agent.agent_name] = result
            agent_results.append(result)
            if result["status"] != "success":
                break

        analysis_context = AgentAnalysisContext.from_agent_results(result_map)
        commander_result: AgentResult | None = None
        planning_result: dict[str, Any] | None = None
        analysis_success = all(result["status"] == "success" for result in agent_results)
        if analysis_success and planning_task is not None:
            try:
                planning_result = coordinate_route_resource_planning(planning_task).to_dict()
                agent_results.extend(_agent_results_from_planning(planning_result))
            except Exception as exc:
                planning_result = _planning_failure_result(exc)

        if analysis_success:
            try:
                commander_result = await self.commander_agent.run(
                    analysis_context,
                    planning_result=planning_result,
                    force_provider=force_provider,
                )
            except Exception as exc:
                commander_result = agent_result(
                    self.commander_agent.agent_name,
                    status="error",
                    output={"error": str(exc)},
                    reasoning=["CommanderAgent failed before producing a valid output."],
                )
            result_map[self.commander_agent.agent_name] = commander_result
            agent_results.append(commander_result)

        return {
            "agent_results": agent_results,
            "analysis_context": analysis_context.to_dict(),
            "commander_result": commander_result,
            "planning_result": planning_result,
            "standard_outputs": standardize_agent_results(agent_results),
        }


def _capability_agents(agents: Sequence[BaseAgent]) -> dict[str, BaseAgent]:
    by_name = {agent.agent_name: agent for agent in agents}
    mapped: dict[str, BaseAgent] = {}
    if "SituationAgent" in by_name:
        mapped["situation_analysis"] = by_name["SituationAgent"]
    if "SpreadAgent" in by_name:
        mapped["spread_forecast"] = by_name["SpreadAgent"]
    if "RiskAgent" in by_name:
        mapped["risk_assessment"] = by_name["RiskAgent"]
    return mapped


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


def _planning_failure_result(exc: Exception) -> dict[str, Any]:
    warning = f"Planning unavailable: {exc}"
    return {
        "success": False,
        "status": "error",
        "task": {},
        "resource_result": {},
        "route_results": [],
        "route_agent_results": {},
        "resource_agent_result": {},
        "selected_resources": [],
        "operational_routes": [],
        "alternative_routes": [],
        "rejected_resources": [],
        "resource_shortage": [],
        "estimated_response": {},
        "warnings": [warning],
        "diagnostics": {
            "coordination_service": "Route-Resource Planning Service",
            "planning_error": str(exc),
            "fallback": "CommanderAgent continued with Situation/Spread/Risk only.",
        },
        "metadata": {"planning_unit": "Route-Resource Planning Service", "llm_used": False},
    }
