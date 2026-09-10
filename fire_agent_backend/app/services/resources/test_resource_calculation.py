"""Tests for the standalone wildfire resource dispatch calculation unit."""

from __future__ import annotations

import unittest
from dataclasses import replace

from app.services.resources import (
    Resource,
    ResourceRequirement,
    ResourceTask,
    build_mountain_resource_inventory,
    calculate_resource_dispatch,
    fire_suppression_task,
    multi_resource_fire_task,
    reconnaissance_task,
)
from app.services.routing import build_mountain_fire_rescue_network, default_fire_engine_profile


class ResourceCalculationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.network = build_mountain_fire_rescue_network()
        self.inventory = build_mountain_resource_inventory()

    def dispatch(self, task: ResourceTask):
        return calculate_resource_dispatch(task, self.inventory, self.network)

    def selected_ids(self, result) -> list[str]:
        return [item["resource_id"] for item in result.selected_resources]

    def rejected(self, result, resource_id: str) -> list[dict]:
        return [item for item in result.rejected_resources if item["resource_id"] == resource_id]

    def candidate(self, result, resource_id: str) -> dict:
        for item in result.candidate_resources:
            if item["resource_id"] == resource_id:
                return item
        raise AssertionError(f"candidate not found: {resource_id}")

    def test_resource_capability_matching(self) -> None:
        result = self.dispatch(fire_suppression_task("balanced"))
        bravo = self.candidate(result, "engine_bravo_paved_fast")

        self.assertTrue(bravo["capability_match"])
        self.assertGreaterEqual(bravo["capability_score"], 1.0)
        self.assertIn("capability_match", bravo["reason_codes"])

    def test_unavailable_resource_excluded(self) -> None:
        result = self.dispatch(fire_suppression_task("balanced"))
        foxtrot = self.rejected(result, "engine_foxtrot_unavailable")

        self.assertTrue(foxtrot)
        self.assertIn("unavailable", foxtrot[0]["reason_codes"])
        self.assertNotIn("engine_foxtrot_unavailable", self.selected_ids(result))

    def test_fastest_response_strategy(self) -> None:
        result = self.dispatch(fire_suppression_task("fastest_response"))

        self.assertTrue(result.success)
        self.assertEqual(["engine_bravo_paved_fast"], self.selected_ids(result))
        self.assertIn("scored_by_fastest_response", result.selected_resources[0]["reason_codes"])

    def test_safest_response_strategy(self) -> None:
        result = self.dispatch(fire_suppression_task("safest_response"))

        self.assertTrue(result.success)
        self.assertEqual(["engine_charlie_safe_ridge"], self.selected_ids(result))
        self.assertLess(result.selected_resources[0]["risk_score"], self.candidate(result, "engine_bravo_paved_fast")["risk_score"])

    def test_balanced_strategy(self) -> None:
        result = self.dispatch(fire_suppression_task("balanced"))

        self.assertTrue(result.success)
        self.assertEqual(["engine_bravo_paved_fast"], self.selected_ids(result))
        self.assertGreater(result.selected_resources[0]["score"], 0)
        self.assertIn("scored_by_balanced", result.selected_resources[0]["reason_codes"])

    def test_nearest_is_not_fastest(self) -> None:
        result = self.dispatch(fire_suppression_task("fastest_response"))
        alpha = self.candidate(result, "engine_alpha_near_steep")
        bravo = self.candidate(result, "engine_bravo_paved_fast")

        self.assertLess(alpha["distance_km"], bravo["distance_km"])
        self.assertLess(bravo["estimated_response_minutes"], alpha["estimated_response_minutes"])
        self.assertEqual("engine_bravo_paved_fast", result.selected_resources[0]["resource_id"])

    def test_fastest_is_not_safest(self) -> None:
        fastest = self.dispatch(fire_suppression_task("fastest_response"))
        safest = self.dispatch(fire_suppression_task("safest_response"))

        self.assertEqual("engine_bravo_paved_fast", fastest.selected_resources[0]["resource_id"])
        self.assertEqual("engine_charlie_safe_ridge", safest.selected_resources[0]["resource_id"])
        self.assertLess(safest.selected_resources[0]["risk_score"], fastest.selected_resources[0]["risk_score"])

    def test_route_eta_comes_from_routing_unit(self) -> None:
        result = self.dispatch(fire_suppression_task("fastest_response"))
        selected = result.selected_resources[0]

        self.assertEqual(selected["estimated_response_minutes"], selected["route"]["estimated_travel_time_minutes"])
        self.assertEqual("astar", selected["route"]["algorithm"])
        self.assertEqual("travel_time", selected["route"]["cost_mode"])

    def test_route_risk_comes_from_routing_unit(self) -> None:
        result = self.dispatch(fire_suppression_task("safest_response"))
        selected = result.selected_resources[0]

        self.assertEqual(selected["risk_score"], selected["route"]["risk_score"])
        self.assertEqual("risk_aware_astar", selected["route"]["algorithm"])
        self.assertGreaterEqual(selected["route"]["risk_cost"], 0.0)

    def test_vehicle_inaccessible_candidate_rejected(self) -> None:
        result = self.dispatch(fire_suppression_task("balanced"))
        echo = self.rejected(result, "engine_echo_trail_blocked")

        self.assertTrue(echo)
        self.assertIn("route_unreachable", echo[0]["reason_codes"])
        self.assertIn("vehicle_inaccessible", echo[0]["reason_codes"])
        self.assertNotIn("engine_echo_trail_blocked", self.selected_ids(result))

    def test_blocked_road_causes_dispatch_change(self) -> None:
        normal = self.dispatch(fire_suppression_task("fastest_response"))
        blocked = self.dispatch(
            replace(fire_suppression_task("fastest_response"), blocked_edge_ids=frozenset({"edge_paved_fast_1"}))
        )

        self.assertEqual("engine_bravo_paved_fast", normal.selected_resources[0]["resource_id"])
        self.assertEqual("engine_charlie_safe_ridge", blocked.selected_resources[0]["resource_id"])
        self.assertTrue(any("blocked_road" in item["reason_codes"] for item in blocked.candidate_resources))

    def test_capability_mismatch_rejected(self) -> None:
        result = self.dispatch(fire_suppression_task("fastest_response"))
        delta = self.rejected(result, "engine_delta_fast_wrong_capability")

        self.assertTrue(delta)
        self.assertIn("capability_mismatch", delta[0]["reason_codes"])
        self.assertIn("fire_suppression", delta[0]["diagnostics"]["missing_capabilities"])

    def test_multiple_resource_allocation(self) -> None:
        result = self.dispatch(multi_resource_fire_task("balanced"))

        self.assertTrue(result.success)
        self.assertEqual(3, len(result.selected_resources))
        self.assertEqual(2, len([item for item in result.selected_resources if item["resource_type"] == "fire_engine"]))
        self.assertEqual(1, len([item for item in result.selected_resources if item["resource_type"] == "fire_team"]))

    def test_no_duplicate_allocation(self) -> None:
        result = self.dispatch(multi_resource_fire_task("balanced"))
        selected_ids = self.selected_ids(result)

        self.assertEqual(len(selected_ids), len(set(selected_ids)))

    def test_resource_shortage(self) -> None:
        result = self.dispatch(fire_suppression_task("balanced", engine_quantity=4))

        self.assertFalse(result.success)
        self.assertEqual("partial", result.status)
        self.assertEqual(1, result.resource_shortage[0]["shortage"])
        self.assertTrue(any("Minimum resource requirements" in warning for warning in result.warnings))

    def test_unreachable_resource_rejected(self) -> None:
        task = replace(
            fire_suppression_task("balanced"),
            blocked_edge_ids=frozenset({"edge_mountain_short_1", "edge_mountain_short_2", "edge_paved_fast_1", "edge_safe_detour_1"}),
        )
        result = self.dispatch(task)
        alpha = self.rejected(result, "engine_alpha_near_steep")

        self.assertTrue(alpha)
        self.assertIn("route_unreachable", alpha[0]["reason_codes"])

    def test_selected_resource_contains_real_route_geometry(self) -> None:
        result = self.dispatch(fire_suppression_task("fastest_response"))
        route = result.selected_resources[0]["route"]

        self.assertEqual("LineString", route["geometry"]["type"])
        self.assertGreaterEqual(len(route["geometry"]["coordinates"]), 2)
        self.assertEqual(route["geometry"]["coordinates"], result.selected_resources[0]["route"]["geometry"]["coordinates"])

    def test_deterministic_result(self) -> None:
        first = self.dispatch(fire_suppression_task("balanced")).to_dict()
        second = self.dispatch(fire_suppression_task("balanced")).to_dict()

        self.assertEqual(first["selected_resources"], second["selected_resources"])
        self.assertEqual(first["candidate_resources"], second["candidate_resources"])
        self.assertEqual(first["resource_shortage"], second["resource_shortage"])

    def test_calculation_unit_independent_from_llm(self) -> None:
        result = self.dispatch(fire_suppression_task("balanced"))

        self.assertFalse(result.metadata["llm_used"])
        self.assertEqual("Resource Calculation Unit", result.metadata["calculation_unit"])

    def test_reconnaissance_uav_uses_direct_flight_estimate(self) -> None:
        result = self.dispatch(reconnaissance_task())

        self.assertTrue(result.success)
        self.assertEqual(["uav_recon_01"], self.selected_ids(result))
        selected = result.selected_resources[0]
        self.assertEqual("direct_air_estimate", selected["route"]["algorithm"])
        self.assertEqual("straight_line_flight_time", selected["accessibility"]["model"])

    def test_unsupported_strategy_raises_error(self) -> None:
        with self.assertRaises(ValueError):
            self.dispatch(fire_suppression_task("nearest_only"))

    def test_missing_target_raises_error(self) -> None:
        with self.assertRaises(ValueError):
            self.dispatch(replace(fire_suppression_task("balanced"), target_node_id="missing_target"))

    def test_ground_resource_missing_origin_rejected(self) -> None:
        resources = [
            Resource(
                resource_id="engine_without_origin",
                resource_type="fire_engine",
                name="Engine without origin",
                capabilities=frozenset({"fire_suppression", "pump"}),
                vehicle_profile=default_fire_engine_profile(),
            )
        ]
        task = ResourceTask(
            task_id="task_missing_origin",
            task_type="fire_suppression",
            target_node_id="incident",
            minimum_resource_requirements=(
                ResourceRequirement("fire_engine", 1, frozenset({"fire_suppression", "pump"})),
            ),
        )
        result = calculate_resource_dispatch(task, resources, self.network)

        self.assertFalse(result.success)
        self.assertEqual("failed", result.status)
        self.assertIn("missing_origin_node", result.rejected_resources[0]["reason_codes"])


if __name__ == "__main__":
    unittest.main()