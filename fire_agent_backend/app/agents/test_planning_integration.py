"""Integration tests for optional Planning capability in the agent pipeline."""

from __future__ import annotations

import asyncio
import unittest
from dataclasses import replace
from types import SimpleNamespace

from app.agents.commander_agent import CommanderAgent
from app.agents.orchestrator import MultiAgentOrchestrator
from app.agents.test_agents import _mock_context
from app.services.planning import PlanningTask
from app.services.resources import ResourceRequirement, build_mountain_resource_inventory
from app.services.routing import build_mountain_fire_rescue_network


class _PlanningFakeProvider:
    async def generate(self, system_prompt, payload):
        return SimpleNamespace(
            provider="test-provider",
            model="test-model",
            content='{"summary":"Planning-aware test decision summary."}',
            used_remote=False,
        )


class CommanderPlanningIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.network = build_mountain_fire_rescue_network()
        self.inventory = build_mountain_resource_inventory()
        self.engine_requirement = (
            ResourceRequirement("fire_engine", 1, frozenset({"fire_suppression", "pump"})),
        )

    def orchestrator(self) -> MultiAgentOrchestrator:
        return MultiAgentOrchestrator(commander_agent=CommanderAgent(llm_provider=_PlanningFakeProvider()))

    def task(self, **overrides) -> PlanningTask:
        data = {
            "task_id": "planning_commander_integration",
            "incident_id": "incident_agent_integration",
            "task_type": "fire_suppression",
            "target_node_id": "incident",
            "priority": "critical",
            "resource_inventory": self.inventory,
            "road_network": self.network,
            "resource_strategy": "balanced",
            "route_objective": "compare",
            "minimum_resource_requirements": self.engine_requirement,
            "route_risk_weight": 20.0,
            "metadata": {"synthetic": True, "scenario_version": "agent-integration-test"},
        }
        data.update(overrides)
        return PlanningTask(**data)

    def run_pipeline(self, planning_task: PlanningTask | None = None) -> dict:
        return asyncio.run(self.orchestrator().run(_mock_context(), planning_task=planning_task))

    def commander_plan(self, result: dict) -> dict:
        return result["commander_result"]["output"]["recommended_plan"]

    def test_no_planning_keeps_existing_main_chain_compatible(self) -> None:
        result = self.run_pipeline(planning_task=None)

        self.assertEqual(
            [item["agent_name"] for item in result["agent_results"]],
            ["SituationAgent", "SpreadAgent", "RiskAgent", "CommanderAgent"],
        )
        self.assertIsNone(result["planning_result"])
        self.assertNotIn("selected_resources", self.commander_plan(result))
        self.assertEqual(
            [item["domain"] for item in result["standard_outputs"]],
            ["situation", "spread", "risk", "command"],
        )

    def test_planning_enabled_feeds_selected_resources_routes_eta_and_risk_to_commander(self) -> None:
        result = self.run_pipeline(self.task())
        planning = result["planning_result"]
        plan = self.commander_plan(result)
        route = planning["operational_routes"][0]
        selected = planning["selected_resources"][0]

        self.assertTrue(planning["success"])
        self.assertEqual("success", planning["status"])
        self.assertEqual(selected["resource_id"], plan["selected_resources"][0]["resource_id"])
        self.assertEqual(route["resource_id"], plan["operational_routes"][0]["resource_id"])
        self.assertEqual(route["eta_minutes"], plan["operational_routes"][0]["eta_minutes"])
        self.assertEqual(route["risk_score"], plan["operational_routes"][0]["risk_score"])
        self.assertEqual(planning["resource_shortage"], [])
        self.assertEqual(
            [item["agent_name"] for item in result["agent_results"]],
            ["SituationAgent", "SpreadAgent", "RiskAgent", "ResourceAgent", "RouteAgent", "CommanderAgent"],
        )

    def test_commander_planning_summary_is_fact_consistent_with_planning_result(self) -> None:
        result = self.run_pipeline(
            self.task(
                minimum_resource_requirements=(
                    ResourceRequirement("fire_engine", 4, frozenset({"fire_suppression", "pump"})),
                )
            )
        )
        planning = result["planning_result"]
        summary = result["commander_result"]["output"]["plan_packet"]["planning_summary"]
        route = planning["operational_routes"][0]

        self.assertEqual("partial", summary["status"])
        self.assertEqual(planning["selected_resources"][0]["resource_id"], summary["selected_resources"][0]["resource_id"])
        self.assertEqual(route["eta_minutes"], summary["operational_routes"][0]["eta_minutes"])
        self.assertEqual(route["risk_score"], summary["operational_routes"][0]["risk_score"])
        self.assertEqual(planning["resource_shortage"][0]["shortage"], summary["shortage"]["items"][0]["shortage"])

    def test_blocked_road_recalculation_propagates_to_commander(self) -> None:
        original = self.run_pipeline(self.task(resource_strategy="fastest_response"))
        blocked = self.run_pipeline(
            self.task(resource_strategy="fastest_response", blocked_edge_ids=frozenset({"edge_paved_fast_1"}))
        )

        original_planning = original["planning_result"]
        blocked_planning = blocked["planning_result"]
        original_plan = self.commander_plan(original)
        blocked_plan = self.commander_plan(blocked)

        self.assertEqual("engine_bravo_paved_fast", original_planning["selected_resources"][0]["resource_id"])
        self.assertEqual("engine_charlie_safe_ridge", blocked_planning["selected_resources"][0]["resource_id"])
        self.assertEqual("engine_bravo_paved_fast", original_plan["selected_resources"][0]["resource_id"])
        self.assertEqual("engine_charlie_safe_ridge", blocked_plan["selected_resources"][0]["resource_id"])
        self.assertNotEqual(
            original_plan["operational_routes"][0]["eta_minutes"],
            blocked_plan["operational_routes"][0]["eta_minutes"],
        )

    def test_resource_unavailable_recalculation_propagates_to_commander(self) -> None:
        updated_inventory = [
            replace(resource, available=False, status="maintenance")
            if resource.resource_id == "engine_bravo_paved_fast"
            else resource
            for resource in self.inventory
        ]
        original = self.run_pipeline(self.task(resource_strategy="fastest_response"))
        changed = self.run_pipeline(self.task(resource_strategy="fastest_response", resource_inventory=updated_inventory))

        self.assertEqual("engine_bravo_paved_fast", self.commander_plan(original)["selected_resources"][0]["resource_id"])
        self.assertEqual("engine_charlie_safe_ridge", self.commander_plan(changed)["selected_resources"][0]["resource_id"])
        self.assertNotEqual(
            self.commander_plan(original)["operational_routes"][0]["resource_id"],
            self.commander_plan(changed)["operational_routes"][0]["resource_id"],
        )

    def test_planning_failure_falls_back_without_fake_routes_or_resources(self) -> None:
        result = self.run_pipeline(self.task(road_network=None))  # type: ignore[arg-type]
        planning = result["planning_result"]
        plan = self.commander_plan(result)

        self.assertEqual("error", planning["status"])
        self.assertFalse(planning["success"])
        self.assertEqual([], planning["selected_resources"])
        self.assertEqual([], planning["operational_routes"])
        self.assertEqual([], plan["selected_resources"])
        self.assertEqual([], plan["operational_routes"])
        self.assertTrue(plan["planning_warnings"])
        self.assertEqual("success", result["commander_result"]["status"])

    def test_planning_agent_results_are_reused_without_duplicate_execution(self) -> None:
        result = self.run_pipeline(self.task())
        names = [item["agent_name"] for item in result["agent_results"]]
        domains = [item["domain"] for item in result["standard_outputs"]]
        planning = result["planning_result"]

        self.assertEqual(1, names.count("ResourceAgent"))
        self.assertEqual(1, names.count("RouteAgent"))
        self.assertEqual(1, domains.count("resource"))
        self.assertEqual(1, domains.count("route"))
        self.assertEqual(
            planning["diagnostics"]["route_agent_called_resource_ids"],
            list(planning["route_agent_results"].keys()),
        )


if __name__ == "__main__":
    unittest.main()
