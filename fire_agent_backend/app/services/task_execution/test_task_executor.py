"""Tests for TaskPlan-driven dynamic execution and trace output."""

from __future__ import annotations

import asyncio
import json
import unittest
from dataclasses import replace
from types import SimpleNamespace

from app.agents.base import agent_result
from app.agents.commander_agent import CommanderAgent
from app.agents.orchestrator import MultiAgentOrchestrator
from app.agents.resource_agent import ResourceAgentTask
from app.agents.route_agent import RouteTask
from app.agents.test_agents import _mock_context
from app.services.planning import PlanningTask
from app.services.resources import ResourceRequirement, build_mountain_resource_inventory
from app.services.task_execution import TaskExecutionContext, TaskPlanExecutor
from app.services.task_planning import NaturalLanguageTaskPlanner, NaturalLanguageTaskRequest, TaskPlan, TaskStep
from app.services.routing import build_mountain_fire_rescue_network

READY_ANALYSIS = {"decision_context": True}
READY_ROUTE = {"road_network": True, "start": True, "destination": True}
READY_RESOURCE = {"road_network": True, "resource_inventory": True, "target": True}
READY_PLANNING = {"planning_task": True, "road_network": True, "resource_inventory": True, "target": True}
READY_FULL = {**READY_ANALYSIS, **READY_PLANNING}


class _FakeProvider:
    async def generate(self, system_prompt, payload):
        return SimpleNamespace(provider="fake", model="fake-command", content='{"summary":"Executor command summary."}', used_remote=False)


class _FailingSituationAgent:
    agent_name = "SituationAgent"

    def run(self, context, prior_results=None):
        return agent_result("SituationAgent", status="error", output={"error": "simulated situation failure"}, reasoning=[])


class TaskPlanExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.network = build_mountain_fire_rescue_network()
        self.inventory = build_mountain_resource_inventory()
        self.engine_requirement = (
            ResourceRequirement("fire_engine", 1, frozenset({"fire_suppression", "pump"})),
        )

    def plan(self, query: str, available_inputs: dict | None = None) -> TaskPlan:
        return asyncio.run(
            NaturalLanguageTaskPlanner().plan(
                NaturalLanguageTaskRequest(query=query, available_inputs=available_inputs or READY_FULL)
            )
        )

    def planning_task(self, **overrides) -> PlanningTask:
        data = {
            "task_id": "executor_planning",
            "incident_id": "executor_incident",
            "task_type": "fire_suppression",
            "target_node_id": "incident",
            "priority": "critical",
            "resource_inventory": self.inventory,
            "road_network": self.network,
            "resource_strategy": "fastest_response",
            "route_objective": "compare",
            "minimum_resource_requirements": self.engine_requirement,
            "metadata": {"synthetic": True, "scenario_version": "executor-test"},
        }
        data.update(overrides)
        return PlanningTask(**data)

    def route_task(self, **overrides) -> RouteTask:
        data = {
            "road_network": self.network,
            "start_node_id": "base",
            "destination_node_id": "incident",
            "objective": "fastest",
            "task_id": "executor_route",
            "metadata": {"synthetic": True},
        }
        data.update(overrides)
        return RouteTask(**data)

    def resource_task(self, **overrides) -> ResourceAgentTask:
        planning = self.planning_task(**overrides)
        return ResourceAgentTask(
            task=planning.to_resource_task(),
            resources=planning.resource_inventory,
            road_network=planning.road_network,
            mode=planning.resource_strategy,
            task_id=planning.task_id,
            incident_id=planning.incident_id,
            metadata={"synthetic": True},
        )

    def execute(self, task_plan: TaskPlan, inputs: TaskExecutionContext) -> dict:
        executor = TaskPlanExecutor(commander_agent=CommanderAgent(llm_provider=_FakeProvider()))
        return asyncio.run(executor.execute(task_plan, inputs))

    def step_statuses(self, result: dict) -> dict[str, str]:
        return {step["capability_id"]: step["status"] for step in result["execution_trace"]["steps"]}

    def test_situation_only_executes_only_situation(self) -> None:
        task_plan = self.plan("现在火势怎么样？", READY_ANALYSIS)
        result = self.execute(task_plan, TaskExecutionContext(decision_context=_mock_context()))

        self.assertEqual(["SituationAgent"], [item["agent_name"] for item in result["agent_results"]])
        self.assertEqual("success", result["overall_status"])
        self.assertEqual(["situation"], [item["domain"] for item in result["standard_outputs"]])
        self.assertIsNone(result["commander_result"])

    def test_situation_spread_executes_without_risk_planning_commander(self) -> None:
        task_plan = self.plan("预测未来三小时火灾蔓延趋势。", READY_ANALYSIS)
        result = self.execute(task_plan, TaskExecutionContext(decision_context=_mock_context()))

        self.assertEqual(["SituationAgent", "SpreadAgent"], [item["agent_name"] for item in result["agent_results"]])
        self.assertNotIn("RiskAgent", [item["agent_name"] for item in result["agent_results"]])
        self.assertIsNone(result["planning_result"])
        self.assertIsNone(result["commander_result"])

    def test_risk_plan_executes_ordered_analysis_only(self) -> None:
        task_plan = self.plan("未来三小时哪些区域风险最高？", READY_ANALYSIS)
        result = self.execute(task_plan, TaskExecutionContext(decision_context=_mock_context()))

        self.assertEqual(["SituationAgent", "SpreadAgent", "RiskAgent"], [item["agent_name"] for item in result["agent_results"]])
        self.assertEqual(["situation_analysis", "spread_forecast", "risk_assessment"], list(self.step_statuses(result)))
        self.assertIsNone(result["commander_result"])

    def test_independent_route_executes_route_agent_only(self) -> None:
        task_plan = self.plan("给消防车规划最快路线。", READY_ROUTE)
        result = self.execute(task_plan, TaskExecutionContext(route_task=self.route_task()))

        self.assertEqual(["RouteAgent"], [item["agent_name"] for item in result["agent_results"]])
        self.assertEqual("success", result["route_result"]["status"])
        self.assertEqual({}, result["analysis_context"]["situation"].get("situation_packet"))

    def test_route_blocked_missing_input_does_not_call_route_agent(self) -> None:
        task_plan = self.plan("给消防车规划最快路线。", {"start": True, "destination": True})
        result = self.execute(task_plan, TaskExecutionContext())

        self.assertEqual([], result["agent_results"])
        self.assertEqual("blocked", self.step_statuses(result)["route_planning"])
        self.assertIn("road_network", result["execution_trace"]["steps"][0]["missing_inputs"])
        self.assertIsNone(result["route_result"])

    def test_independent_resource_executes_resource_agent_only(self) -> None:
        task_plan = self.plan("应该调哪些消防资源？", READY_RESOURCE)
        result = self.execute(task_plan, TaskExecutionContext(resource_task=self.resource_task()))

        self.assertEqual(["ResourceAgent"], [item["agent_name"] for item in result["agent_results"]])
        self.assertEqual("success", result["resource_result"]["status"])

    def test_planning_executes_planning_service_and_reuses_internal_agents(self) -> None:
        task_plan = self.plan("调度消防资源并规划救援路线。", READY_PLANNING)
        result = self.execute(task_plan, TaskExecutionContext(planning_task=self.planning_task()))
        names = [item["agent_name"] for item in result["agent_results"]]

        self.assertEqual(["route_resource_planning"], result["task_plan"]["selected_capabilities"])
        self.assertEqual(1, names.count("ResourceAgent"))
        self.assertEqual(1, names.count("RouteAgent"))
        self.assertEqual("success", result["planning_result"]["status"])

    def test_full_emergency_executes_analysis_planning_commander(self) -> None:
        task_plan = self.plan("判断未来三小时火灾蔓延趋势，并给出消防员救援路线以及完整救援方案。", READY_FULL)
        result = self.execute(task_plan, TaskExecutionContext(decision_context=_mock_context(), planning_task=self.planning_task()))

        self.assertEqual(
            ["SituationAgent", "SpreadAgent", "RiskAgent", "ResourceAgent", "RouteAgent", "CommanderAgent"],
            [item["agent_name"] for item in result["agent_results"]],
        )
        self.assertEqual("success", result["overall_status"])
        self.assertEqual("success", result["commander_result"]["status"])

    def test_partial_emergency_blocks_planning_and_commander_by_dependency(self) -> None:
        task_plan = self.plan("判断未来三小时火灾蔓延趋势，并给出消防员救援路线以及完整救援方案。", READY_ANALYSIS)
        result = self.execute(task_plan, TaskExecutionContext(decision_context=_mock_context()))
        statuses = self.step_statuses(result)

        self.assertEqual("success", statuses["situation_analysis"])
        self.assertEqual("success", statuses["spread_forecast"])
        self.assertEqual("success", statuses["risk_assessment"])
        self.assertEqual("blocked", statuses["route_resource_planning"])
        self.assertEqual("blocked", statuses["command_synthesis"])
        self.assertEqual("partial", result["overall_status"])
        self.assertIsNone(result["planning_result"])
        self.assertIsNone(result["commander_result"])

    def test_dependency_failure_blocks_dependent_steps(self) -> None:
        task_plan = self.plan("未来三小时哪些区域风险最高？", READY_ANALYSIS)
        executor = TaskPlanExecutor(agents={"situation_analysis": _FailingSituationAgent()})
        result = asyncio.run(executor.execute(task_plan, TaskExecutionContext(decision_context=_mock_context())))
        statuses = self.step_statuses(result)

        self.assertEqual("failed", statuses["situation_analysis"])
        self.assertEqual("blocked", statuses["spread_forecast"])
        self.assertEqual("blocked", statuses["risk_assessment"])
        self.assertEqual("failed", result["overall_status"])

    def test_independent_failure_isolation_keeps_successful_unrelated_step(self) -> None:
        task_plan = TaskPlan(
            original_query="current situation and route",
            intent="mixed_independent",
            requested_outputs=("current fire situation", "route planning"),
            selected_capabilities=("situation_analysis", "route_planning"),
            execution_steps=(
                TaskStep("step_1_situation_analysis", "situation_analysis", "Situation Analysis", "SituationAgent", required_inputs=("decision_context",)),
                TaskStep("step_2_route_planning", "route_planning", "Route Planning", "RouteAgent", required_inputs=("road_network", "start", "destination")),
            ),
            dependencies={"situation_analysis": (), "route_planning": ()},
            required_inputs=("decision_context", "road_network", "start", "destination"),
            missing_inputs=(),
            executable=True,
            status="ready",
            warnings=(),
            planner_source="deterministic",
        )
        bad_route = self.route_task(objective="unsupported")  # type: ignore[arg-type]
        result = self.execute(task_plan, TaskExecutionContext(decision_context=_mock_context(), route_task=bad_route))
        statuses = self.step_statuses(result)

        self.assertEqual("success", statuses["situation_analysis"])
        self.assertEqual("failed", statuses["route_planning"])
        self.assertEqual("partial", result["overall_status"])
        self.assertEqual(["SituationAgent", "RouteAgent"], [item["agent_name"] for item in result["agent_results"]])

    def test_commander_only_runs_when_selected(self) -> None:
        result = self.execute(self.plan("现在火势怎么样？", READY_ANALYSIS), TaskExecutionContext(decision_context=_mock_context()))

        self.assertNotIn("CommanderAgent", [item["agent_name"] for item in result["agent_results"]])
        self.assertIsNone(result["commander_result"])

    def test_dynamic_recalculation_updates_planning_and_commander(self) -> None:
        task_plan = self.plan("判断未来三小时火灾蔓延趋势，并给出消防员救援路线以及完整救援方案。", READY_FULL)
        original = self.execute(task_plan, TaskExecutionContext(decision_context=_mock_context(), planning_task=self.planning_task()))
        blocked = self.execute(
            task_plan,
            TaskExecutionContext(
                decision_context=_mock_context(),
                planning_task=self.planning_task(blocked_edge_ids=frozenset({"edge_paved_fast_1"})),
            ),
        )

        self.assertEqual("engine_bravo_paved_fast", original["planning_result"]["selected_resources"][0]["resource_id"])
        self.assertEqual("engine_charlie_safe_ridge", blocked["planning_result"]["selected_resources"][0]["resource_id"])
        self.assertEqual("engine_bravo_paved_fast", original["commander_result"]["output"]["recommended_plan"]["selected_resources"][0]["resource_id"])
        self.assertEqual("engine_charlie_safe_ridge", blocked["commander_result"]["output"]["recommended_plan"]["selected_resources"][0]["resource_id"])

    def test_resource_unavailable_recalculation_updates_planning(self) -> None:
        task_plan = self.plan("调度消防资源并规划救援路线。", READY_PLANNING)
        updated_inventory = [
            replace(resource, available=False, status="maintenance")
            if resource.resource_id == "engine_bravo_paved_fast"
            else resource
            for resource in self.inventory
        ]
        result = self.execute(
            task_plan,
            TaskExecutionContext(planning_task=self.planning_task(resource_inventory=updated_inventory)),
        )

        self.assertEqual("engine_charlie_safe_ridge", result["planning_result"]["selected_resources"][0]["resource_id"])

    def test_execution_trace_has_order_status_duration_and_no_large_outputs(self) -> None:
        task_plan = self.plan("判断未来三小时火灾蔓延趋势，并给出消防员救援路线以及完整救援方案。", READY_FULL)
        result = self.execute(task_plan, TaskExecutionContext(decision_context=_mock_context(), planning_task=self.planning_task()))
        trace = result["execution_trace"]

        self.assertEqual("success", trace["status"])
        self.assertEqual(
            ["situation_analysis", "spread_forecast", "risk_assessment", "route_resource_planning", "command_synthesis"],
            [step["capability_id"] for step in trace["steps"]],
        )
        self.assertTrue(all(step["duration_ms"] is None or step["duration_ms"] >= 0 for step in trace["steps"]))
        serialized_trace = json.dumps(trace, ensure_ascii=False)
        self.assertNotIn("reasoning", serialized_trace)
        self.assertNotIn("fire_front_steps", serialized_trace)
        self.assertNotIn("coordinates", serialized_trace)

    def test_orchestrator_task_plan_mode_delegates_to_executor(self) -> None:
        task_plan = self.plan("现在火势怎么样？", READY_ANALYSIS)
        result = asyncio.run(MultiAgentOrchestrator().run(_mock_context(), task_plan=task_plan))

        self.assertIn("execution_trace", result)
        self.assertEqual(["SituationAgent"], [item["agent_name"] for item in result["agent_results"]])

    def test_orchestrator_legacy_mode_remains_fixed_compatible(self) -> None:
        result = asyncio.run(MultiAgentOrchestrator(commander_agent=CommanderAgent(llm_provider=_FakeProvider())).run(_mock_context()))

        self.assertEqual(
            ["SituationAgent", "SpreadAgent", "RiskAgent", "CommanderAgent"],
            [item["agent_name"] for item in result["agent_results"]],
        )
        self.assertNotIn("execution_trace", result)


if __name__ == "__main__":
    unittest.main()
