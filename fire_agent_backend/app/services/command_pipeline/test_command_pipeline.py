"""Tests for the natural-language command pipeline."""

from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace

from app.agents.commander_agent import CommanderAgent
from app.agents.resource_agent import ResourceAgentTask
from app.agents.route_agent import RouteTask
from app.agents.test_agents import _mock_context
from app.services.command_pipeline import CommandRequest, NaturalLanguageCommandPipeline
from app.services.planning import PlanningTask
from app.services.resources import ResourceRequirement, build_mountain_resource_inventory
from app.services.routing import build_mountain_fire_rescue_network
from app.services.task_execution import TaskPlanExecutor
from app.services.task_planning import NaturalLanguageTaskPlanner


class _FakeCommanderProvider:
    async def generate(self, system_prompt, payload):
        return SimpleNamespace(
            provider="fake-command-provider",
            model="fake-command-model",
            content='{"summary":"Pipeline command summary."}',
            used_remote=False,
        )


class _UnavailablePlannerProvider:
    async def generate(self, system_prompt, payload):
        raise RuntimeError("planner provider unavailable")


class CommandPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.network = build_mountain_fire_rescue_network()
        self.inventory = build_mountain_resource_inventory()
        self.pipeline = NaturalLanguageCommandPipeline(
            executor=TaskPlanExecutor(
                commander_agent=CommanderAgent(llm_provider=_FakeCommanderProvider()),
            )
        )

    def run_pipeline(self, request: CommandRequest):
        return asyncio.run(self.pipeline.run(request))

    def planning_task(self) -> PlanningTask:
        return PlanningTask(
            task_id="planning_command_pipeline",
            incident_id="incident_command_pipeline",
            task_type="fire_suppression",
            target_node_id="incident",
            priority="critical",
            resource_inventory=self.inventory,
            road_network=self.network,
            resource_strategy="fastest_response",
            route_objective="compare",
            minimum_resource_requirements=(
                ResourceRequirement("fire_engine", 1, frozenset({"fire_suppression", "pump"})),
            ),
            metadata={"synthetic": True, "scenario_version": "command-pipeline-test"},
        )

    def route_task(self) -> RouteTask:
        return RouteTask(
            road_network=self.network,
            start_node_id="base",
            destination_node_id="incident",
            objective="compare",
            risk_weight=20.0,
            metadata={"synthetic": True, "scenario_version": "command-pipeline-test"},
        )

    def resource_task(self) -> ResourceAgentTask:
        task = self.planning_task()
        return ResourceAgentTask(
            task=task.to_resource_task(),
            resources=task.resource_inventory,
            road_network=task.road_network,
            mode=task.resource_strategy,
            metadata={"synthetic": True, "scenario_version": "command-pipeline-test"},
        )

    def agent_names(self, result) -> list[str]:
        return [item["agent_name"] for item in result.agent_results]

    def capability_statuses(self, result) -> dict[str, str]:
        return {step["capability_id"]: step["status"] for step in result.execution_trace["steps"]}

    def test_situation_query_runs_situation_only(self) -> None:
        result = self.run_pipeline(
            CommandRequest(
                user_query="What is the current fire situation?",
                decision_context=_mock_context(),
            )
        )

        self.assertEqual("success", result.status)
        self.assertEqual(["SituationAgent"], self.agent_names(result))
        self.assertEqual(("situation_analysis",), tuple(result.task_plan["selected_capabilities"]))

    def test_spread_query_runs_situation_and_spread(self) -> None:
        result = self.run_pipeline(
            CommandRequest(
                user_query="Forecast the fire spread for the next 3 hours.",
                decision_context=_mock_context(),
            )
        )

        self.assertEqual("success", result.status)
        self.assertEqual(["SituationAgent", "SpreadAgent"], self.agent_names(result))

    def test_risk_query_runs_situation_spread_and_risk(self) -> None:
        result = self.run_pipeline(
            CommandRequest(
                user_query="Show wildfire risk and hazard now.",
                decision_context=_mock_context(),
            )
        )

        self.assertEqual("success", result.status)
        self.assertEqual(["SituationAgent", "SpreadAgent", "RiskAgent"], self.agent_names(result))

    def test_route_query_with_route_task_runs_route_agent(self) -> None:
        result = self.run_pipeline(
            CommandRequest(
                user_query="Find the fastest route to the incident.",
                route_task=self.route_task(),
            )
        )

        self.assertEqual("success", result.status)
        self.assertEqual(["RouteAgent"], self.agent_names(result))
        self.assertTrue(result.metadata["available_inputs"]["road_network"])
        self.assertTrue(result.metadata["available_inputs"]["start"])
        self.assertTrue(result.metadata["available_inputs"]["destination"])

    def test_route_query_without_route_inputs_is_blocked(self) -> None:
        result = self.run_pipeline(CommandRequest(user_query="Find a route to the incident."))

        self.assertEqual("blocked", result.status)
        self.assertEqual([], self.agent_names(result))
        self.assertEqual({"road_network", "start", "destination"}, set(result.missing_inputs))
        self.assertFalse(result.metadata["synthetic_defaults_used"])

    def test_route_resource_planning_with_planning_task_runs_planning_once(self) -> None:
        result = self.run_pipeline(
            CommandRequest(
                user_query="Route and resource dispatch.",
                planning_task=self.planning_task(),
            )
        )

        self.assertEqual("success", result.status)
        self.assertIn("ResourceAgent", self.agent_names(result))
        self.assertIn("RouteAgent", self.agent_names(result))
        self.assertIsNotNone(result.planning_result)
        self.assertEqual(["engine_bravo_paved_fast"], [item["resource_id"] for item in result.planning_result["selected_resources"]])
        self.assertEqual({"route_resource_planning": "success"}, self.capability_statuses(result))

    def test_route_resource_planning_without_planning_task_is_blocked(self) -> None:
        result = self.run_pipeline(CommandRequest(user_query="Route and resource dispatch."))

        self.assertEqual("blocked", result.status)
        self.assertEqual([], self.agent_names(result))
        self.assertEqual({"planning_task", "road_network", "resource_inventory", "target"}, set(result.missing_inputs))
        self.assertFalse(result.metadata["available_inputs"]["planning_task"])
        self.assertFalse(result.metadata["synthetic_defaults_used"])

    def test_full_emergency_with_planning_task_runs_commander(self) -> None:
        result = self.run_pipeline(
            CommandRequest(
                user_query="Forecast spread, assess risk, plan route and resource dispatch, then give command recommendation.",
                decision_context=_mock_context(),
                planning_task=self.planning_task(),
            )
        )

        self.assertEqual("success", result.status)
        self.assertEqual(
            ["SituationAgent", "SpreadAgent", "RiskAgent", "ResourceAgent", "RouteAgent", "CommanderAgent"],
            self.agent_names(result),
        )
        self.assertIsNotNone(result.commander_result)
        self.assertIn("planning_summary", result.commander_result["output"]["decision_summary"])
        self.assertEqual(["engine_bravo_paved_fast"], [item["resource_id"] for item in result.planning_result["selected_resources"]])

    def test_full_emergency_without_planning_task_is_partial(self) -> None:
        result = self.run_pipeline(
            CommandRequest(
                user_query="Forecast spread, assess risk, plan route and resource dispatch, then give command recommendation.",
                decision_context=_mock_context(),
            )
        )

        self.assertEqual("partial", result.status)
        statuses = self.capability_statuses(result)
        self.assertEqual("success", statuses["situation_analysis"])
        self.assertEqual("success", statuses["spread_forecast"])
        self.assertEqual("success", statuses["risk_assessment"])
        self.assertEqual("blocked", statuses["route_resource_planning"])
        self.assertEqual("blocked", statuses["command_synthesis"])
        self.assertIn("road_network", result.missing_inputs)
        self.assertIn("resource_inventory", result.missing_inputs)
        self.assertIn("target", result.missing_inputs)
        self.assertIsNone(result.commander_result)

    def test_llm_planner_failure_falls_back_inside_planner_boundary(self) -> None:
        pipeline = NaturalLanguageCommandPipeline(
            planner=NaturalLanguageTaskPlanner(llm_provider=_UnavailablePlannerProvider()),
            executor=TaskPlanExecutor(commander_agent=CommanderAgent(llm_provider=_FakeCommanderProvider())),
        )
        result = asyncio.run(
            pipeline.run(
                CommandRequest(
                    user_query="What is the current fire situation?",
                    decision_context=_mock_context(),
                )
            )
        )

        self.assertEqual("success", result.status)
        self.assertEqual("llm_fallback", result.metadata["planner_source"])
        self.assertTrue(result.metadata["fallback_used"])
        self.assertTrue(any("deterministic fallback" in warning for warning in result.warnings))

    def test_command_result_to_dict_exposes_required_fields(self) -> None:
        result = self.run_pipeline(
            CommandRequest(
                user_query="What is the current fire situation?",
                decision_context=_mock_context(),
                metadata={"request_id": "cmd_test"},
            )
        )
        payload = result.to_dict()

        self.assertEqual(
            {
                "query",
                "status",
                "task_plan",
                "execution_trace",
                "agent_results",
                "standard_outputs",
                "analysis_context",
                "planning_result",
                "commander_result",
                "missing_inputs",
                "warnings",
                "metadata",
            },
            set(payload),
        )
        self.assertEqual("cmd_test", payload["metadata"]["request_id"])
        self.assertTrue(payload["metadata"]["available_inputs_derived"])


if __name__ == "__main__":
    unittest.main()
