"""Tests for route-resource planning coordination."""

from __future__ import annotations

import unittest
from dataclasses import replace

from app.services.planning import PlanningTask, coordinate_route_resource_planning
from app.services.resources import ResourceRequirement, build_mountain_resource_inventory
from app.services.routing import build_mountain_fire_rescue_network


class RouteResourcePlanningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.network = build_mountain_fire_rescue_network()
        self.inventory = build_mountain_resource_inventory()
        self.engine_requirement = (
            ResourceRequirement("fire_engine", 1, frozenset({"fire_suppression", "pump"})),
        )

    def task(self, **overrides) -> PlanningTask:
        data = {
            "task_id": "planning_mountain_fire",
            "incident_id": "incident_001",
            "task_type": "fire_suppression",
            "target_node_id": "incident",
            "priority": "critical",
            "resource_inventory": self.inventory,
            "road_network": self.network,
            "resource_strategy": "balanced",
            "route_objective": "compare",
            "minimum_resource_requirements": self.engine_requirement,
            "route_risk_weight": 20.0,
            "metadata": {"synthetic": True, "scenario_version": "unit-test"},
        }
        data.update(overrides)
        return PlanningTask(**data)

    def plan(self, **overrides):
        return coordinate_route_resource_planning(self.task(**overrides)).to_dict()

    def selected_ids(self, result: dict) -> list[str]:
        return [item["resource_id"] for item in result["selected_resources"]]

    def test_basic_coordination_returns_selected_resource_and_operational_route(self) -> None:
        result = self.plan()

        self.assertTrue(result["success"])
        self.assertEqual("success", result["status"])
        self.assertEqual(["engine_bravo_paved_fast"], self.selected_ids(result))
        self.assertEqual(1, len(result["operational_routes"]))
        self.assertEqual("engine_bravo_paved_fast", result["operational_routes"][0]["resource_id"])

    def test_selected_resource_route_binding_is_explicit(self) -> None:
        result = self.plan()
        selected = result["selected_resources"][0]
        operational = result["operational_routes"][0]

        self.assertEqual(selected["resource_id"], operational["resource_id"])
        self.assertEqual(selected["origin"], operational["origin"])
        self.assertEqual(selected["target"], operational["target"])
        self.assertEqual(selected["route"], operational["route"])
        self.assertEqual(selected["estimated_response_minutes"], operational["eta_minutes"])
        self.assertEqual(selected["risk_score"], operational["risk_score"])
        self.assertEqual(selected["route"]["geometry"], operational["geometry"])

    def test_fastest_resource_plan(self) -> None:
        result = self.plan(resource_strategy="fastest_response")

        self.assertEqual(["engine_bravo_paved_fast"], self.selected_ids(result))
        self.assertEqual("fastest_response", result["operational_routes"][0]["source_strategy"])

    def test_safest_resource_plan(self) -> None:
        result = self.plan(resource_strategy="safest_response")

        self.assertEqual(["engine_charlie_safe_ridge"], self.selected_ids(result))
        self.assertLess(result["operational_routes"][0]["risk_score"], 0.1)

    def test_alternative_routes_are_generated_for_selected_ground_resource(self) -> None:
        result = self.plan()
        alternatives = result["alternative_routes"]
        objectives = {objective for item in alternatives for objective in item["objectives"]}

        self.assertTrue(alternatives)
        self.assertEqual({"shortest", "fastest", "safest"}, objectives)
        self.assertEqual(len(alternatives), len({_route_identity(item["route"]) for item in alternatives}))

    def test_resource_shortage_is_preserved(self) -> None:
        result = self.plan(
            minimum_resource_requirements=(
                ResourceRequirement("fire_engine", 4, frozenset({"fire_suppression", "pump"})),
            )
        )

        self.assertEqual("partial", result["status"])
        self.assertFalse(result["success"])
        self.assertEqual(1, result["resource_shortage"][0]["shortage"])
        self.assertTrue(any("Minimum resource requirements" in warning for warning in result["warnings"]))

    def test_capability_mismatch_remains_visible(self) -> None:
        result = self.plan()
        rejected = {item["resource_id"]: item for item in result["rejected_resources"]}

        self.assertIn("engine_delta_fast_wrong_capability", rejected)
        self.assertIn("capability_mismatch", rejected["engine_delta_fast_wrong_capability"]["reason_codes"])

    def test_vehicle_inaccessible_remains_visible(self) -> None:
        result = self.plan()
        rejected = {item["resource_id"]: item for item in result["rejected_resources"]}

        self.assertIn("engine_echo_trail_blocked", rejected)
        self.assertIn("vehicle_inaccessible", rejected["engine_echo_trail_blocked"]["reason_codes"])
        self.assertIn("route_unreachable", rejected["engine_echo_trail_blocked"]["reason_codes"])

    def test_road_blocked_recalculation_updates_resource_and_route(self) -> None:
        original = self.plan(resource_strategy="fastest_response")
        blocked = self.plan(
            resource_strategy="fastest_response",
            blocked_edge_ids=frozenset({"edge_paved_fast_1"}),
        )

        self.assertEqual(["engine_bravo_paved_fast"], self.selected_ids(original))
        self.assertEqual(["engine_charlie_safe_ridge"], self.selected_ids(blocked))
        self.assertNotEqual(original["operational_routes"][0]["route"]["route_edges"], blocked["operational_routes"][0]["route"]["route_edges"])

    def test_risk_change_recalculation_updates_resource_route_risk(self) -> None:
        original = self.plan(resource_strategy="safest_response")
        changed = self.plan(
            resource_strategy="safest_response",
            edge_risk_overrides={
                "edge_safe_detour_1": 0.99,
                "edge_safe_detour_2": 0.99,
                "edge_safe_detour_3": 0.99,
            },
        )

        self.assertEqual(["engine_charlie_safe_ridge"], self.selected_ids(original))
        self.assertEqual(["engine_bravo_paved_fast"], self.selected_ids(changed))
        self.assertNotEqual(original["operational_routes"][0]["risk_score"], changed["operational_routes"][0]["risk_score"])

    def test_resource_unavailable_recalculation_updates_dispatch_and_route(self) -> None:
        original = self.plan(resource_strategy="fastest_response")
        updated_inventory = [
            replace(resource, available=False, status="maintenance")
            if resource.resource_id == "engine_bravo_paved_fast"
            else resource
            for resource in self.inventory
        ]
        changed = self.plan(resource_strategy="fastest_response", resource_inventory=updated_inventory)

        self.assertEqual(["engine_bravo_paved_fast"], self.selected_ids(original))
        self.assertEqual(["engine_charlie_safe_ridge"], self.selected_ids(changed))
        self.assertNotEqual(original["operational_routes"][0]["origin"], changed["operational_routes"][0]["origin"])

    def test_uav_does_not_call_road_route_agent(self) -> None:
        result = self.plan(
            task_type="reconnaissance",
            resource_strategy="fastest_response",
            minimum_resource_requirements=(ResourceRequirement("uav", 1, frozenset({"aerial_recon"})),),
        )
        operational = result["operational_routes"][0]

        self.assertEqual(["uav_recon_01"], self.selected_ids(result))
        self.assertEqual({}, result["route_agent_results"])
        self.assertFalse(result["diagnostics"]["uav_road_routing_called"])
        self.assertEqual("resource_direct_air_estimate", operational["route_source"])
        self.assertEqual("direct_air_estimate", operational["route"]["algorithm"])

    def test_real_geojson_eta_risk_and_metrics_are_preserved(self) -> None:
        result = self.plan()
        operational = result["operational_routes"][0]

        self.assertEqual("LineString", operational["geometry"]["type"])
        self.assertGreater(operational["eta_minutes"], 0)
        self.assertGreaterEqual(operational["risk_score"], 0)
        self.assertIn("max_slope_percent", operational["terrain_metrics"])
        self.assertIn("forest_road_distance_km", operational["road_metrics"])
        self.assertIn("inaccessible_edges_avoided", operational["accessibility"])

    def test_operational_route_is_consistent_with_resource_route(self) -> None:
        result = self.plan()
        consistency = result["operational_routes"][0]["consistency"]

        self.assertEqual("consistent", consistency["status"])
        self.assertTrue(consistency["matches_resource_dispatch_route"])
        self.assertTrue(consistency["eta_matches_resource"])
        self.assertTrue(consistency["risk_matches_resource"])
        self.assertTrue(consistency["geometry_matches_resource"])
        self.assertEqual([], result["diagnostics"]["resource_route_conflicts"])

    def test_route_preference_operational_route_is_role_differentiated(self) -> None:
        result = self.plan(
            resource_strategy="fastest_response",
            route_objective="safest",
            operational_route_source="route_preference",
        )
        operational = result["operational_routes"][0]

        self.assertEqual("route_agent_route_preference", operational["route_source"])
        self.assertEqual("role_differentiated", operational["consistency"]["status"])
        self.assertFalse(operational["consistency"]["eta_matches_resource"])
        self.assertTrue(result["diagnostics"]["resource_route_conflicts"])

    def test_planning_result_contains_required_sections(self) -> None:
        result = self.plan()

        for key in [
            "resource_result",
            "route_results",
            "selected_resources",
            "operational_routes",
            "alternative_routes",
            "resource_shortage",
            "warnings",
            "diagnostics",
        ]:
            self.assertIn(key, result)
        self.assertIn("standard_outputs", result["metadata"])

    def test_deterministic_planning_result(self) -> None:
        first = self.plan()
        second = self.plan()

        self.assertEqual(first["selected_resources"], second["selected_resources"])
        self.assertEqual(first["operational_routes"], second["operational_routes"])
        self.assertEqual(first["alternative_routes"], second["alternative_routes"])

    def test_no_llm_dependency(self) -> None:
        result = self.plan()

        self.assertFalse(result["metadata"]["llm_used"])
        self.assertFalse(result["diagnostics"]["llm_used"])
        self.assertIsNone(result["metadata"]["standard_outputs"]["resource"]["provenance"]["provider"])


def _route_identity(route: dict) -> tuple:
    edges = tuple(route.get("route_edges") or [])
    if edges:
        return ("edges", edges)
    return ("geometry", tuple(tuple(point) for point in route.get("geometry", {}).get("coordinates", [])))


if __name__ == "__main__":
    unittest.main()
