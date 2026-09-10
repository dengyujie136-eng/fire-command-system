"""Tests for the independent ResourceAgent integration layer."""

from __future__ import annotations

import unittest
from dataclasses import replace

from app.agents.resource_agent import ResourceAgent, ResourceAgentTask
from app.agents.schema import standardize_agent_result
from app.services.resources import (
    Resource,
    ResourceRequirement,
    ResourceTask,
    build_mountain_resource_inventory,
    fire_suppression_task,
    reconnaissance_task,
)
from app.services.routing import build_mountain_fire_rescue_network


class ResourceAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.network = build_mountain_fire_rescue_network()
        self.inventory = build_mountain_resource_inventory()
        self.agent = ResourceAgent()

    def run_agent(self, task: ResourceTask | None = None, mode: str = "balanced", resources=None):
        context = ResourceAgentTask(
            task=task or fire_suppression_task("balanced"),
            resources=self.inventory if resources is None else resources,
            road_network=self.network,
            mode=mode,  # type: ignore[arg-type]
            metadata={"resource_source": "unit_test_inventory", "synthetic": True},
        )
        return self.agent.run(context)

    def recommended(self, result) -> dict:
        plan = result["output"]["recommended_plan"]
        self.assertIsNotNone(plan)
        return plan

    def selected_ids(self, plan: dict) -> list[str]:
        return [item["resource_id"] for item in plan["selected_resources"]]

    def test_fastest_task_selects_fastest_real_dispatch(self) -> None:
        result = self.run_agent(mode="fastest_response")
        plan = self.recommended(result)

        self.assertEqual("success", result["status"])
        self.assertEqual("fastest_response", plan["strategy"])
        self.assertEqual(["engine_bravo_paved_fast"], self.selected_ids(plan))

    def test_safest_task_selects_lowest_risk_dispatch(self) -> None:
        result = self.run_agent(mode="safest_response")
        plan = self.recommended(result)

        self.assertEqual("safest_response", plan["strategy"])
        self.assertEqual(["engine_charlie_safe_ridge"], self.selected_ids(plan))
        self.assertLess(plan["selected_resources"][0]["risk_score"], 0.1)

    def test_capability_first_task_returns_real_capability_scored_plan(self) -> None:
        result = self.run_agent(mode="capability_first")
        plan = self.recommended(result)

        self.assertEqual("capability_first", plan["strategy"])
        self.assertTrue(plan["success"])
        self.assertIn("scored_by_capability_first", plan["selected_resources"][0]["reason_codes"])

    def test_balanced_task_selects_balanced_dispatch(self) -> None:
        result = self.run_agent(mode="balanced")
        plan = self.recommended(result)

        self.assertEqual("balanced", plan["strategy"])
        self.assertEqual(["engine_bravo_paved_fast"], self.selected_ids(plan))
        self.assertIn("scored_by_balanced", plan["selected_resources"][0]["reason_codes"])

    def test_compare_task_runs_multiple_real_strategies(self) -> None:
        result = self.run_agent(mode="compare")
        output = result["output"]

        self.assertEqual(4, len(output["dispatch_plans"]))
        self.assertEqual(
            {"fastest_response", "safest_response", "capability_first", "balanced"},
            {plan["strategy"] for plan in output["dispatch_plans"]},
        )
        self.assertIn(output["recommended_plan"], output["dispatch_plans"])
        self.assertIn("fastest_response", output["dispatch_comparison"])
        self.assertIn("safest_response", output["dispatch_comparison"])
        self.assertIn("balanced", output["dispatch_comparison"])

    def test_selected_resource_preserves_real_dispatch_fields(self) -> None:
        plan = self.recommended(self.run_agent(mode="fastest_response"))
        selected = plan["selected_resources"][0]

        self.assertEqual("engine_bravo_paved_fast", selected["resource_id"])
        self.assertIn("route", selected)
        self.assertIn("score", selected)
        self.assertIn("reason_codes", selected)
        self.assertEqual(selected["estimated_response_minutes"], selected["route"]["estimated_travel_time_minutes"])

    def test_rejected_resources_are_exposed_with_reason_codes(self) -> None:
        plan = self.recommended(self.run_agent(mode="balanced"))
        rejected = {item["resource_id"]: item for item in plan["rejected_resources"]}

        self.assertIn("engine_delta_fast_wrong_capability", rejected)
        self.assertIn("capability_mismatch", rejected["engine_delta_fast_wrong_capability"]["reason_codes"])
        self.assertIn("engine_foxtrot_unavailable", rejected)
        self.assertIn("unavailable", rejected["engine_foxtrot_unavailable"]["reason_codes"])
        self.assertIn("engine_echo_trail_blocked", rejected)
        self.assertIn("route_unreachable", rejected["engine_echo_trail_blocked"]["reason_codes"])

    def test_shortage_is_kept_visible(self) -> None:
        result = self.run_agent(task=fire_suppression_task("balanced", engine_quantity=4), mode="balanced")
        plan = self.recommended(result)

        self.assertFalse(plan["success"])
        self.assertEqual("partial", plan["status"])
        self.assertEqual(1, plan["resource_shortage"][0]["shortage"])
        self.assertTrue(result["output"]["resource_summary"]["has_shortage"])
        self.assertTrue(any("Minimum resource requirements" in warning for warning in result["output"]["warnings"]))

    def test_route_geometry_is_forwarded_for_cesium(self) -> None:
        plan = self.recommended(self.run_agent(mode="fastest_response"))
        route = plan["selected_resources"][0]["route"]

        self.assertEqual("LineString", route["geometry"]["type"])
        self.assertGreaterEqual(len(route["geometry"]["coordinates"]), 2)

    def test_eta_is_forwarded_from_calculation_unit(self) -> None:
        plan = self.recommended(self.run_agent(mode="fastest_response"))
        selected = plan["selected_resources"][0]

        self.assertGreater(selected["estimated_response_minutes"], 0)
        self.assertEqual(selected["estimated_response_minutes"], selected["route"]["estimated_travel_time_minutes"])
        self.assertEqual(selected["estimated_response_minutes"], plan["summary_metrics"]["max_eta_minutes"])

    def test_risk_is_forwarded_from_routing_unit(self) -> None:
        plan = self.recommended(self.run_agent(mode="safest_response"))
        selected = plan["selected_resources"][0]

        self.assertEqual(selected["risk_score"], selected["route"]["risk_score"])
        self.assertIn("risk_score", selected)
        self.assertIn("max_risk_score", plan["summary_metrics"])

    def test_terrain_and_road_metrics_are_exposed(self) -> None:
        plan = self.recommended(self.run_agent(mode="fastest_response"))
        route = plan["selected_resources"][0]["route"]

        self.assertIn("terrain_metrics", route)
        self.assertIn("road_metrics", route)
        self.assertIn("max_slope_percent", route["terrain_metrics"])
        self.assertIn("forest_road_distance_km", route["road_metrics"])
        self.assertIn("unpaved_distance_km", route["road_metrics"])

    def test_capability_explanation_is_available(self) -> None:
        result = self.run_agent(mode="balanced")
        explanations = result["output"]["analysis"]["rejection_explanations"]
        delta = [item for item in explanations if item["resource_id"] == "engine_delta_fast_wrong_capability"][0]

        self.assertIn("capability_mismatch", delta["reason_codes"])
        self.assertIn("required capabilities", delta["summary"])
        self.assertIn("missing_capabilities", delta["diagnostics"])

    def test_unreachable_dispatch_returns_structured_no_recommendation(self) -> None:
        task = replace(
            fire_suppression_task("balanced"),
            blocked_edge_ids=frozenset(
                {
                    "edge_mountain_short_1",
                    "edge_mountain_short_2",
                    "edge_paved_fast_1",
                    "edge_safe_detour_1",
                    "edge_safe_detour_2",
                }
            ),
        )
        result = self.run_agent(task=task, mode="compare")

        self.assertEqual("success", result["status"])
        self.assertIsNone(result["output"]["recommended_plan"])
        self.assertEqual([], result["output"]["selected_resources"])
        self.assertTrue(any("No dispatchable resource" in warning for warning in result["output"]["warnings"]))

    def test_blocked_road_changes_dispatch_selection(self) -> None:
        normal = self.recommended(self.run_agent(mode="fastest_response"))
        blocked = self.recommended(
            self.run_agent(
                task=replace(fire_suppression_task("fastest_response"), blocked_edge_ids=frozenset({"edge_paved_fast_1"})),
                mode="fastest_response",
            )
        )

        self.assertEqual(["engine_bravo_paved_fast"], self.selected_ids(normal))
        self.assertEqual(["engine_charlie_safe_ridge"], self.selected_ids(blocked))

    def test_compare_recommendation_is_deterministic(self) -> None:
        first = self.run_agent(mode="compare")["output"]
        second = self.run_agent(mode="compare")["output"]

        self.assertEqual(first["recommended_plan"]["plan_id"], second["recommended_plan"]["plan_id"])
        self.assertEqual(first["dispatch_comparison"], second["dispatch_comparison"])

    def test_agent_result_compatibility(self) -> None:
        result = self.run_agent(mode="balanced")

        self.assertIsInstance(result, dict)
        self.assertEqual("ResourceAgent", result["agent_name"])
        self.assertEqual("success", result["status"])
        self.assertIn("output", result)
        self.assertIn("reasoning", result)

    def test_standard_output_domain_and_layers(self) -> None:
        standard = standardize_agent_result(self.run_agent(mode="fastest_response"))
        layers = standard["visualization"]["layers"]

        self.assertEqual("agent-output/v1", standard["schema_version"])
        self.assertEqual("resource", standard["domain"])
        self.assertEqual("ResourceAgent", standard["agent_name"])
        self.assertTrue(any(layer["layer_type"] == "resource_target" for layer in layers))
        self.assertTrue(any(layer["layer_type"] == "resource_point" and layer["resource_status"] == "selected" for layer in layers))
        self.assertTrue(any(layer["layer_type"] == "resource_route" for layer in layers))

    def test_no_llm_is_used(self) -> None:
        result = self.run_agent(mode="compare")

        self.assertFalse(result["output"]["algorithm"]["metrics"]["llm_used"])
        self.assertFalse(result["output"]["provenance"]["llm_used"])
        self.assertTrue(any("No LLM call" in item for item in result["reasoning"]))

    def test_empty_inventory_is_structured_not_crashing(self) -> None:
        result = self.run_agent(mode="balanced", resources=[])
        plan = self.recommended(result)

        self.assertEqual("success", result["status"])
        self.assertEqual("failed", plan["status"])
        self.assertEqual([], plan["selected_resources"])
        self.assertTrue(any("inventory is empty" in warning.lower() for warning in result["output"]["warnings"]))

    def test_no_matching_capability_is_structured(self) -> None:
        task = ResourceTask(
            task_id="medical_task",
            task_type="fire_suppression",
            target_node_id="incident",
            minimum_resource_requirements=(
                ResourceRequirement("medical", 1, frozenset({"medical_support"})),
            ),
        )
        result = self.run_agent(task=task, mode="balanced")
        plan = self.recommended(result)

        self.assertEqual("failed", plan["status"])
        self.assertEqual([], plan["selected_resources"])
        self.assertEqual(1, plan["resource_shortage"][0]["shortage"])

    def test_reconnaissance_uav_direct_estimate_is_labeled(self) -> None:
        result = self.run_agent(task=reconnaissance_task(), mode="fastest_response")
        plan = self.recommended(result)
        selected = plan["selected_resources"][0]
        route_layer = [
            layer for layer in result["output"]["visualization"]["layers"] if layer.get("layer_type") == "resource_route"
        ][0]

        self.assertEqual("uav_recon_01", selected["resource_id"])
        self.assertEqual("direct_air_estimate", selected["route"]["algorithm"])
        self.assertTrue(route_layer["properties"]["is_simplified_direct_estimate"])
        self.assertTrue(any("simplified direct" in factor for factor in result["output"]["analysis"]["key_factors"]))

    def test_invalid_mode_returns_error_agent_result(self) -> None:
        result = self.run_agent(mode="nearest_only")

        self.assertEqual("error", result["status"])
        self.assertIn("Unsupported resource dispatch mode", result["output"]["warnings"][0])


if __name__ == "__main__":
    unittest.main()
