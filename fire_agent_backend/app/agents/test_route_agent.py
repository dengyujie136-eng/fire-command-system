"""Independent tests for RouteAgent."""

from __future__ import annotations

import unittest
from dataclasses import replace

from app.agents.route_agent import RouteAgent, RouteTask
from app.agents.schema import SCHEMA_VERSION, standardize_agent_result
from app.services.routing import RoutingRequest, build_mountain_fire_rescue_network


class RouteAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.network = build_mountain_fire_rescue_network()
        self.agent = RouteAgent()

    def task(self, **overrides: object) -> RouteTask:
        base = RouteTask(
            road_network=self.network,
            start_node_id="base",
            destination_node_id="incident",
            objective="compare",
            risk_weight=20.0,
            metadata={"source": "synthetic_mountain_rescue_network", "synthetic": True},
        )
        return replace(base, **overrides)

    def candidate(self, result, objective: str) -> dict:
        for candidate in result["output"]["candidate_routes"]:
            if candidate["objective"] == objective:
                return candidate
        raise AssertionError(f"candidate not found: {objective}")

    def test_shortest_task(self) -> None:
        result = self.agent.run(self.task(objective="shortest"))
        shortest = self.candidate(result, "shortest")

        self.assertEqual("success", result["status"])
        self.assertEqual(["edge_mountain_short_1", "edge_mountain_short_2"], shortest["route_edges"])
        self.assertEqual(shortest["route_id"], result["output"]["recommended_route"]["route_id"])

    def test_fastest_task(self) -> None:
        result = self.agent.run(self.task(objective="fastest"))
        fastest = self.candidate(result, "fastest")

        self.assertEqual("success", result["status"])
        self.assertEqual(["edge_paved_fast_1", "edge_paved_fast_2"], fastest["route_edges"])
        self.assertEqual("travel_time", fastest["cost_mode"])

    def test_safest_task(self) -> None:
        result = self.agent.run(self.task(objective="safest"))
        safest = self.candidate(result, "safest")

        self.assertEqual("success", result["status"])
        self.assertEqual(["edge_safe_detour_1", "edge_safe_detour_2", "edge_safe_detour_3"], safest["route_edges"])
        self.assertEqual("risk_aware_astar", safest["algorithm"])

    def test_compare_task(self) -> None:
        result = self.agent.run(self.task(objective="compare"))
        objectives = [candidate["objective"] for candidate in result["output"]["candidate_routes"]]

        self.assertEqual("success", result["status"])
        self.assertEqual(["shortest", "fastest", "safest"], objectives)
        self.assertEqual({"shortest", "fastest", "safest"}, set(result["output"]["route_comparison"]))

    def test_candidate_routes_include_real_geometry(self) -> None:
        result = self.agent.run(self.task(objective="compare"))

        for candidate in result["output"]["candidate_routes"]:
            self.assertEqual("LineString", candidate["geometry"]["type"])
            self.assertGreaterEqual(len(candidate["geometry"]["coordinates"]), 2)
            self.assertEqual(len(candidate["route_nodes"]), len(candidate["geometry"]["coordinates"]))

    def test_recommended_route_comes_from_candidate_result(self) -> None:
        result = self.agent.run(self.task(objective="compare"))
        recommended = result["output"]["recommended_route"]
        candidates = {candidate["route_id"]: candidate for candidate in result["output"]["candidate_routes"]}

        self.assertIn(recommended["route_id"], candidates)
        self.assertEqual(candidates[recommended["route_id"]]["geometry"], recommended["geometry"])
        self.assertTrue(any("calculated candidate" in reason for reason in result["reasoning"]))

    def test_terrain_metrics_are_preserved(self) -> None:
        result = self.agent.run(self.task(objective="shortest"))
        shortest = self.candidate(result, "shortest")

        self.assertIn("terrain_metrics", shortest)
        self.assertGreater(shortest["terrain_metrics"]["max_slope_percent"], 10.0)
        self.assertIn("terrain_metrics", result["output"]["visualization"]["layers"][0]["properties"])

    def test_road_metrics_are_preserved(self) -> None:
        result = self.agent.run(self.task(objective="safest"))
        safest = self.candidate(result, "safest")

        self.assertIn("road_metrics", safest)
        self.assertGreater(safest["road_metrics"]["unpaved_distance_km"], 0.0)
        self.assertEqual(0.0, safest["road_metrics"]["forest_road_distance_km"])

    def test_vehicle_accessibility_is_preserved(self) -> None:
        result = self.agent.run(self.task(objective="shortest"))
        shortest = self.candidate(result, "shortest")

        self.assertIn("accessibility", shortest)
        self.assertIn("edge_narrow_trail_1", shortest["accessibility"]["inaccessible_edges_avoided"])
        self.assertTrue(any("Vehicle-inaccessible" in warning for warning in result["output"]["warnings"]))

    def test_blocked_road_reroutes_fastest(self) -> None:
        result = self.agent.run(
            self.task(
                objective="fastest",
                blocked_edge_ids=frozenset({"edge_paved_fast_1"}),
            )
        )
        fastest = self.candidate(result, "fastest")

        self.assertEqual(["edge_safe_detour_1", "edge_safe_detour_2", "edge_safe_detour_3"], fastest["route_edges"])
        self.assertIn("edge_paved_fast_1", fastest["blocked_edges_avoided"])
        self.assertTrue(any("Blocked edges skipped" in warning for warning in result["output"]["warnings"]))

    def test_unreachable_returns_structured_failure_without_fake_route(self) -> None:
        result = self.agent.run(
            self.task(
                objective="fastest",
                blocked_edge_ids=frozenset(
                    {"edge_mountain_short_1", "edge_paved_fast_1", "edge_safe_detour_1"}
                ),
            )
        )
        fastest = self.candidate(result, "fastest")

        self.assertEqual("success", result["status"])
        self.assertFalse(result["output"]["route_summary"]["reachable"])
        self.assertFalse(fastest["success"])
        self.assertEqual([], fastest["route_edges"])
        self.assertEqual({"type": "LineString", "coordinates": []}, fastest["geometry"])
        self.assertIsNone(result["output"]["recommended_route"])
        self.assertTrue(any("No reachable route" in warning for warning in result["output"]["warnings"]))

    def test_agent_result_format_is_compatible(self) -> None:
        result = self.agent.run(self.task(objective="compare"))

        self.assertEqual({"agent_name", "status", "output", "reasoning"}, set(result))
        self.assertEqual("RouteAgent", result["agent_name"])
        self.assertIn("route_summary", result["output"])
        self.assertIn("candidate_routes", result["output"])
        self.assertIn("recommended_route", result["output"])
        self.assertIsInstance(result["reasoning"], list)

    def test_standard_agent_output_conversion(self) -> None:
        result = self.agent.run(self.task(objective="compare"))
        standard = standardize_agent_result(result)

        self.assertEqual(SCHEMA_VERSION, standard["schema_version"])
        self.assertEqual("RouteAgent", standard["agent_name"])
        self.assertEqual("route", standard["domain"])
        self.assertEqual("route", standard["visualization"]["layers"][0]["type"])
        self.assertIn("candidate_routes", standard["algorithm"]["result"])
        self.assertIn("recommended_route", standard["decision"])
        self.assertEqual("RouteAgent", standard["provenance"]["source_agent"])

    def test_route_agent_does_not_depend_on_llm(self) -> None:
        result = self.agent.run(self.task(objective="compare"))

        self.assertIsNone(result["output"]["provenance"]["provider"])
        self.assertIsNone(result["output"]["provenance"]["model"])
        self.assertTrue(any("No LLM call" in reason for reason in result["reasoning"]))

    def test_start_missing_returns_error(self) -> None:
        result = self.agent.run(self.task(start_node_id="missing_start"))

        self.assertEqual("error", result["status"])
        self.assertIn("Unknown road node", result["output"]["warnings"][0])
        self.assertEqual([], result["output"]["candidate_routes"])

    def test_destination_missing_returns_error(self) -> None:
        result = self.agent.run(self.task(destination_node_id="missing_destination"))

        self.assertEqual("error", result["status"])
        self.assertIn("Unknown road node", result["output"]["warnings"][0])
        self.assertEqual([], result["output"]["candidate_routes"])

    def test_unsupported_objective_returns_error(self) -> None:
        result = self.agent.run(self.task(objective="balanced"))

        self.assertEqual("error", result["status"])
        self.assertIn("Unsupported route objective", result["output"]["warnings"][0])

    def test_light_vehicle_objective_uses_supplied_vehicle(self) -> None:
        result = self.agent.run(self.task(objective="shortest", vehicle="light_utility_vehicle"))
        shortest = self.candidate(result, "shortest")

        self.assertEqual(["edge_narrow_trail_1", "edge_narrow_trail_2"], shortest["route_edges"])
        self.assertEqual("light_utility_vehicle", shortest["accessibility"]["vehicle_type"])

    def test_routing_request_input_is_supported(self) -> None:
        result = self.agent.run(
            RoutingRequest(
                network=self.network,
                start_node_id="base",
                destination_node_id="incident",
                algorithm="astar",
                cost_mode="travel_time",
                metadata={"objective": "fastest", "source": "synthetic_mountain_rescue_network"},
            )
        )

        self.assertEqual("success", result["status"])
        self.assertEqual("fastest", result["output"]["route_summary"]["objective"])
        self.assertEqual(["edge_paved_fast_1", "edge_paved_fast_2"], self.candidate(result, "fastest")["route_edges"])

    def test_unreachable_compare_has_no_visual_layers(self) -> None:
        result = self.agent.run(
            self.task(
                objective="compare",
                blocked_edge_ids=frozenset(
                    {"edge_mountain_short_1", "edge_paved_fast_1", "edge_safe_detour_1"}
                ),
            )
        )

        self.assertEqual("success", result["status"])
        self.assertEqual([], result["output"]["visualization"]["layers"])
        self.assertIsNone(result["output"]["recommended_route"])


if __name__ == "__main__":
    unittest.main()