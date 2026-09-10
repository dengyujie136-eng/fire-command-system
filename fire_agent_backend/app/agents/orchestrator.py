"""Sequential orchestrator for the decision agent pipeline."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.agents.base import AgentResult, BaseAgent, agent_result
from app.agents.commander_agent import CommanderAgent
from app.agents.context import AgentAnalysisContext, DecisionContext
from app.agents.risk_agent import RiskAgent
from app.agents.schema import standardize_agent_results
from app.agents.situation_agent import SituationAgent
from app.agents.spread_agent import SpreadAgent


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

    async def run(self, context: DecisionContext, force_provider: str | None = None) -> dict[str, Any]:
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
        if all(result["status"] == "success" for result in agent_results):
            try:
                commander_result = await self.commander_agent.run(
                    analysis_context,
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
            "standard_outputs": standardize_agent_results(agent_results),
        }
