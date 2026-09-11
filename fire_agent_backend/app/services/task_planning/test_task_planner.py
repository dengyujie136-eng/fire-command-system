"""Tests for the natural-language Task Planner and Capability Registry."""

from __future__ import annotations

import asyncio
import json
import unittest
from types import SimpleNamespace

from app.services.task_planning import CapabilityRegistry, NaturalLanguageTaskPlanner, NaturalLanguageTaskRequest, default_registry


READY_ANALYSIS = {"decision_context": True}
READY_ROUTE = {"road_network": True, "start": True, "destination": True}
READY_RESOURCE = {"road_network": True, "resource_inventory": True, "target": True}
READY_PLANNING = {"planning_task": True, "road_network": True, "resource_inventory": True, "target": True}
READY_FULL = {**READY_ANALYSIS, **READY_PLANNING}


class _FakeProvider:
    def __init__(self, content: str | Exception) -> None:
        self.content = content

    async def generate(self, system_prompt, payload):
        if isinstance(self.content, Exception):
            raise self.content
        return SimpleNamespace(provider="fake", model="fake-task-planner", content=self.content, used_remote=False)


def plan(query: str, available_inputs: dict | None = None, *, language: str = "zh") -> dict:
    request = NaturalLanguageTaskRequest(query=query, language=language, available_inputs=available_inputs or READY_FULL)
    result = asyncio.run(NaturalLanguageTaskPlanner().plan(request))
    return result.to_dict()


class TaskPlanningTests(unittest.TestCase):
    def test_registry_contains_current_capabilities(self) -> None:
        registry = default_registry()
        self.assertEqual(
            registry.selectable_ids(),
            (
                "situation_analysis",
                "spread_forecast",
                "risk_assessment",
                "route_planning",
                "resource_dispatch",
                "route_resource_planning",
                "command_synthesis",
            ),
        )
        planning = registry.get("route_resource_planning")
        self.assertEqual("Planning Service", planning.provider)
        self.assertEqual(("planning_task", "road_network", "resource_inventory", "target"), planning.required_inputs)
        self.assertEqual(("route_planning", "resource_dispatch"), planning.subsumes)

    def test_current_fire_situation_selects_situation_only(self) -> None:
        result = plan("现在火势怎么样？", READY_ANALYSIS)

        self.assertEqual(["situation_analysis"], result["selected_capabilities"])
        self.assertEqual("ready", result["status"])
        self.assertTrue(result["executable"])

    def test_spread_forecast_selects_situation_and_spread(self) -> None:
        result = plan("预测未来三小时火灾蔓延趋势。", READY_ANALYSIS)

        self.assertEqual(["situation_analysis", "spread_forecast"], result["selected_capabilities"])
        self.assertEqual({"spread_forecast": ["situation_analysis"]}, {"spread_forecast": result["dependencies"]["spread_forecast"]})

    def test_risk_analysis_selects_situation_spread_risk(self) -> None:
        result = plan("未来三小时哪些区域风险最高？", READY_ANALYSIS)

        self.assertEqual(["situation_analysis", "spread_forecast", "risk_assessment"], result["selected_capabilities"])
        self.assertEqual(["situation_analysis", "spread_forecast"], result["dependencies"]["risk_assessment"])

    def test_route_request_is_identified_and_checks_missing_road_network(self) -> None:
        result = plan("给消防车规划最快路线。", {"start": True, "destination": True})

        self.assertEqual(["route_planning"], result["selected_capabilities"])
        self.assertEqual("blocked", result["status"])
        self.assertFalse(result["executable"])
        self.assertIn("road_network", result["missing_inputs"])

    def test_route_request_ready_when_route_inputs_are_available(self) -> None:
        result = plan("给消防车规划最快路线。", READY_ROUTE)

        self.assertEqual(["route_planning"], result["selected_capabilities"])
        self.assertTrue(result["executable"])

    def test_resource_request_selects_resource_dispatch(self) -> None:
        result = plan("应该调哪些消防资源？", READY_RESOURCE)

        self.assertEqual(["resource_dispatch"], result["selected_capabilities"])
        self.assertTrue(result["executable"])

    def test_route_resource_request_selects_planning_without_duplicates(self) -> None:
        result = plan("调度消防资源并规划救援路线。", READY_PLANNING)

        self.assertEqual(["route_resource_planning"], result["selected_capabilities"])
        self.assertNotIn("route_planning", result["selected_capabilities"])
        self.assertNotIn("resource_dispatch", result["selected_capabilities"])

    def test_full_emergency_request_decomposes_to_analysis_planning_command(self) -> None:
        result = plan("判断未来三小时火灾蔓延趋势，并给出消防员救援路线以及完整救援方案。", READY_FULL)

        self.assertEqual(
            ["situation_analysis", "spread_forecast", "risk_assessment", "route_resource_planning", "command_synthesis"],
            result["selected_capabilities"],
        )
        self.assertEqual(
            ["situation_analysis", "spread_forecast", "risk_assessment", "route_resource_planning"],
            result["dependencies"]["command_synthesis"],
        )
        self.assertTrue(result["executable"])

    def test_full_emergency_missing_planning_inputs_is_partial_not_synthetic(self) -> None:
        result = plan(
            "判断未来三小时火灾蔓延趋势，并给出消防员救援路线以及完整救援方案。",
            {"decision_context": True},
        )

        self.assertEqual("partial", result["status"])
        self.assertFalse(result["executable"])
        self.assertIn("route_resource_planning", result["blocked_steps"])
        self.assertIn("planning_task", result["missing_inputs"])
        self.assertIn("road_network", result["missing_inputs"])
        self.assertIn("resource_inventory", result["missing_inputs"])
        self.assertIn("target", result["missing_inputs"])
        self.assertFalse(result["metadata"]["synthetic_defaults_used"])

    def test_missing_resource_inventory_blocks_planning(self) -> None:
        result = plan("调度消防资源并规划救援路线。", {"planning_task": True, "road_network": True, "target": True})

        self.assertEqual("blocked", result["status"])
        self.assertIn("resource_inventory", result["missing_inputs"])

    def test_missing_target_blocks_planning(self) -> None:
        result = plan("调度消防资源并规划救援路线。", {"planning_task": True, "road_network": True, "resource_inventory": True})

        self.assertEqual("blocked", result["status"])
        self.assertIn("target", result["missing_inputs"])

    def test_capability_whitelist_rejects_unknown_tools(self) -> None:
        registry = CapabilityRegistry()

        with self.assertRaises(ValueError):
            registry.validate(["firefighter_super_agent"])

    def test_dependency_order_is_preserved(self) -> None:
        result = plan("未来三小时哪些区域风险最高？", READY_ANALYSIS)
        order = result["selected_capabilities"]

        self.assertLess(order.index("situation_analysis"), order.index("spread_forecast"))
        self.assertLess(order.index("spread_forecast"), order.index("risk_assessment"))

    def test_llm_valid_structured_output_is_validated(self) -> None:
        content = json.dumps(
            {
                "intent": "risk_assessment",
                "requested_outputs": ["risk assessment"],
                "capabilities": ["risk_assessment"],
            }
        )
        request = NaturalLanguageTaskRequest(query="请判断风险。", available_inputs=READY_ANALYSIS)
        planner = NaturalLanguageTaskPlanner(llm_provider=_FakeProvider(content))
        result = asyncio.run(planner.plan(request)).to_dict()

        self.assertEqual("llm", result["planner_source"])
        self.assertEqual(["situation_analysis", "spread_forecast", "risk_assessment"], result["selected_capabilities"])

    def test_llm_malformed_json_uses_deterministic_fallback(self) -> None:
        request = NaturalLanguageTaskRequest(query="预测未来三小时火灾蔓延趋势。", available_inputs=READY_ANALYSIS)
        planner = NaturalLanguageTaskPlanner(llm_provider=_FakeProvider("not json"))
        result = asyncio.run(planner.plan(request)).to_dict()

        self.assertEqual("llm_fallback", result["planner_source"])
        self.assertTrue(result["fallback_used"])
        self.assertEqual(["situation_analysis", "spread_forecast"], result["selected_capabilities"])

    def test_llm_unknown_capability_uses_validation_fallback(self) -> None:
        content = json.dumps({"intent": "bad", "requested_outputs": [], "capabilities": ["emergency_magic_route"]})
        request = NaturalLanguageTaskRequest(query="给消防车规划最快路线。", available_inputs=READY_ROUTE)
        planner = NaturalLanguageTaskPlanner(llm_provider=_FakeProvider(content))
        result = asyncio.run(planner.plan(request)).to_dict()

        self.assertEqual("llm_fallback", result["planner_source"])
        self.assertEqual(["route_planning"], result["selected_capabilities"])

    def test_llm_unavailable_uses_deterministic_fallback(self) -> None:
        request = NaturalLanguageTaskRequest(query="现在火势怎么样？", available_inputs=READY_ANALYSIS)
        planner = NaturalLanguageTaskPlanner(llm_provider=_FakeProvider(RuntimeError("provider down")))
        result = asyncio.run(planner.plan(request)).to_dict()

        self.assertEqual("llm_fallback", result["planner_source"])
        self.assertEqual(["situation_analysis"], result["selected_capabilities"])

    def test_llm_operational_fact_fields_are_ignored(self) -> None:
        content = json.dumps(
            {
                "intent": "route_planning",
                "requested_outputs": ["route planning"],
                "capabilities": ["route_planning"],
                "eta_minutes": 12,
                "route_geometry": {"type": "LineString"},
            }
        )
        request = NaturalLanguageTaskRequest(query="给消防车规划最快路线。", available_inputs=READY_ROUTE)
        planner = NaturalLanguageTaskPlanner(llm_provider=_FakeProvider(content))
        result = asyncio.run(planner.plan(request)).to_dict()

        self.assertEqual("llm", result["planner_source"])
        self.assertTrue(any("operational fact" in warning for warning in result["warnings"]))
        self.assertNotIn("eta_minutes", result)
        self.assertNotIn("route_geometry", result)

    def test_english_smoke_spread_forecast(self) -> None:
        result = plan("Forecast wildfire spread for the next three hours.", READY_ANALYSIS, language="en")

        self.assertEqual(["situation_analysis", "spread_forecast"], result["selected_capabilities"])

    def test_deterministic_fallback_reproducibility(self) -> None:
        first = plan("调度消防资源并规划救援路线。", READY_PLANNING)
        second = plan("调度消防资源并规划救援路线。", READY_PLANNING)

        self.assertEqual(first, second)

    def test_planner_never_generates_operational_facts(self) -> None:
        result = plan("调度消防资源并规划救援路线。", READY_PLANNING)
        serialized = json.dumps(result, ensure_ascii=False)

        self.assertNotIn("eta_minutes", serialized)
        self.assertNotIn("route_geometry", serialized)
        self.assertNotIn("risk_score", serialized)
        self.assertNotIn("resource_shortage", serialized)
        self.assertNotIn("resource_count", serialized)


if __name__ == "__main__":
    unittest.main()
