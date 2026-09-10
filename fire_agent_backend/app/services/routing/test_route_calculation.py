from __future__ import annotations

import math
import unittest
from dataclasses import replace

from app.services.routing import (
    RoadEdge,
    RoadNetwork,
    RoadNode,
    RoutingRequest,
    build_mountain_fire_rescue_network,
    build_risk_tradeoff_network,
    calculate_route,
    compare_route_algorithms,
    light_utility_vehicle_profile,
)


class RouteCalculationUnitTest(unittest.TestCase):
    def setUp(self) -> None:
        self.network = build_risk_tradeoff_network()
        self.mountain_network = build_mountain_fire_rescue_network()

    def request(self, **overrides: object) -> RoutingRequest:
        base = RoutingRequest(
            network=self.network,
            start_node_id="start",
            destination_node_id="goal",
            metadata={"source": "synthetic_unit_test_network"},
        )
        return replace(base, **overrides)

    def mountain_request(self, **overrides: object) -> RoutingRequest:
        base = RoutingRequest(
            network=self.mountain_network,
            start_node_id="base",
            destination_node_id="incident",
            algorithm="astar",
            metadata={"source": "synthetic_mountain_rescue_network"},
        )
        return replace(base, **overrides)

    def single_edge_eta(self, edge: RoadEdge) -> float:
        network = RoadNetwork(
            nodes=[RoadNode("start", 0.0, 0.0), RoadNode("goal", 0.01, 0.0)],
            edges=[replace(edge, from_node_id="start", to_node_id="goal")],
        )
        result = calculate_route(
            RoutingRequest(
                network=network,
                start_node_id="start",
                destination_node_id="goal",
                algorithm="astar",
                cost_mode="travel_time",
            )
        )
        self.assertTrue(result.success, result.warnings)
        return result.estimated_travel_time_minutes

    def assert_route_edges(self, result, edge_ids: list[str]) -> None:
        self.assertTrue(result.success, result.warnings)
        self.assertEqual(edge_ids, result.route_edges)

    def test_dijkstra_returns_shortest_path(self) -> None:
        result = calculate_route(self.request(algorithm="dijkstra"))

        self.assertTrue(result.success)
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.route_edges, ["edge_short_1", "edge_short_2"])
        self.assertGreater(result.distance_km, 0)
        self.assertGreater(result.estimated_travel_time_minutes, 0)

    def test_astar_returns_shortest_path(self) -> None:
        result = calculate_route(self.request(algorithm="astar"))

        self.assertTrue(result.success)
        self.assertEqual(result.route_edges, ["edge_short_1", "edge_short_2"])
        self.assertEqual(result.geometry["type"], "LineString")

    def test_dijkstra_and_astar_are_consistent_for_same_cost(self) -> None:
        dijkstra = calculate_route(self.request(algorithm="dijkstra"))
        astar = calculate_route(self.request(algorithm="astar"))

        self.assertEqual(dijkstra.route_edges, astar.route_edges)
        self.assertAlmostEqual(dijkstra.total_cost, astar.total_cost, places=4)
        self.assertAlmostEqual(dijkstra.distance_km, astar.distance_km, places=4)

    def test_risk_aware_astar_avoids_high_risk_route(self) -> None:
        result = calculate_route(self.request(algorithm="risk_aware_astar", risk_weight=8.0))

        self.assertTrue(result.success)
        self.assertEqual(result.route_edges, ["edge_safe_1", "edge_safe_2", "edge_safe_3"])
        self.assertNotIn("edge_short_1", result.route_edges)
        self.assertLess(result.risk_score, 0.1)
        self.assertGreater(result.risk_cost, 0)

    def test_risk_weight_changes_route_selection(self) -> None:
        low_risk_weight = calculate_route(self.request(algorithm="risk_aware_astar", risk_weight=0.1))
        high_risk_weight = calculate_route(self.request(algorithm="risk_aware_astar", risk_weight=8.0))

        self.assertEqual(low_risk_weight.route_edges, ["edge_short_1", "edge_short_2"])
        self.assertEqual(high_risk_weight.route_edges, ["edge_safe_1", "edge_safe_2", "edge_safe_3"])
        self.assertLess(high_risk_weight.risk_score, low_risk_weight.risk_score)

    def test_blocked_edge_triggers_reroute(self) -> None:
        normal = calculate_route(self.request(algorithm="dijkstra"))
        rerouted = calculate_route(
            self.request(algorithm="dijkstra", blocked_edge_ids=frozenset({"edge_short_1"}))
        )

        self.assertEqual(normal.route_edges, ["edge_short_1", "edge_short_2"])
        self.assertTrue(rerouted.success)
        self.assertEqual(rerouted.route_edges, ["edge_safe_1", "edge_safe_2", "edge_safe_3"])
        self.assertNotIn("edge_short_1", rerouted.route_edges)
        self.assertIn("edge_short_1", rerouted.blocked_edges_avoided)
        self.assertTrue(any("Blocked edges skipped" in warning for warning in rerouted.warnings))
        self.assertGreater(rerouted.distance_km, normal.distance_km)
        self.assertGreater(rerouted.estimated_travel_time_minutes, 0)

    def test_unreachable_returns_clear_failure(self) -> None:
        result = calculate_route(
            self.request(
                algorithm="astar",
                blocked_edge_ids=frozenset({"edge_short_1", "edge_safe_1"}),
            )
        )

        self.assertFalse(result.success)
        self.assertEqual(result.status, "unreachable")
        self.assertEqual(result.route_nodes, [])
        self.assertEqual(result.route_edges, [])
        self.assertEqual(result.geometry, {"type": "LineString", "coordinates": []})
        self.assertTrue(math.isinf(result.total_cost))
        self.assertIn("edge_short_1", result.blocked_edges_avoided)
        self.assertIn("edge_safe_1", result.blocked_edges_avoided)
        self.assertTrue(result.warnings)

    def test_route_result_geometry_contains_start_and_destination(self) -> None:
        result = calculate_route(self.request(algorithm="risk_aware_astar", risk_weight=8.0))
        coordinates = result.geometry["coordinates"]

        self.assertGreaterEqual(len(coordinates), 2)
        self.assertEqual(coordinates[0], [101.0, 28.0])
        self.assertEqual(coordinates[-1], [101.02, 28.0])

    def test_distance_eta_risk_and_total_cost_are_consistent(self) -> None:
        result = calculate_route(self.request(algorithm="risk_aware_astar", risk_weight=8.0))

        self.assertGreater(result.distance_km, 0)
        self.assertGreater(result.estimated_travel_time_minutes, 0)
        self.assertGreaterEqual(result.risk_score, 0)
        self.assertLessEqual(result.risk_score, 1)
        self.assertGreater(result.total_cost, result.distance_km)

    def test_comparison_runs_all_algorithms(self) -> None:
        results = compare_route_algorithms(self.request(risk_weight=8.0))

        self.assertEqual([item.algorithm for item in results], ["dijkstra", "astar", "risk_aware_astar"])
        self.assertTrue(all(item.success for item in results))
        self.assertNotEqual(results[0].route_edges, results[2].route_edges)

    def test_to_dict_keeps_existing_fields_and_adds_terrain_fields(self) -> None:
        result_dict = calculate_route(self.request(algorithm="astar")).to_dict()

        for key in (
            "success",
            "status",
            "route_nodes",
            "route_edges",
            "distance_km",
            "estimated_travel_time_minutes",
            "risk_score",
            "geometry",
            "terrain_metrics",
            "road_metrics",
            "accessibility",
            "warnings",
        ):
            self.assertIn(key, result_dict)

    def test_mountain_shortest_prefers_steep_forest_route(self) -> None:
        result = calculate_route(self.mountain_request(cost_mode="distance"))

        self.assert_route_edges(result, ["edge_mountain_short_1", "edge_mountain_short_2"])
        self.assertAlmostEqual(2.0, result.distance_km)
        self.assertGreater(result.terrain_metrics["max_slope_percent"], 10.0)

    def test_mountain_fastest_prefers_longer_paved_route(self) -> None:
        result = calculate_route(self.mountain_request(cost_mode="travel_time"))

        self.assert_route_edges(result, ["edge_paved_fast_1", "edge_paved_fast_2"])
        self.assertAlmostEqual(3.0, result.distance_km)
        self.assertLess(result.estimated_travel_time_minutes, 6.0)

    def test_mountain_shortest_and_fastest_are_different(self) -> None:
        shortest = calculate_route(self.mountain_request(cost_mode="distance"))
        fastest = calculate_route(self.mountain_request(cost_mode="travel_time"))

        self.assertNotEqual(shortest.route_edges, fastest.route_edges)
        self.assertLess(shortest.distance_km, fastest.distance_km)
        self.assertGreater(shortest.estimated_travel_time_minutes, fastest.estimated_travel_time_minutes)

    def test_mountain_safest_prefers_low_risk_fire_access_route(self) -> None:
        result = calculate_route(
            self.mountain_request(
                algorithm="risk_aware_astar",
                cost_mode="travel_time",
                risk_weight=20.0,
            )
        )

        self.assert_route_edges(result, ["edge_safe_detour_1", "edge_safe_detour_2", "edge_safe_detour_3"])
        self.assertLess(result.metadata["risk_exposure"], 0.3)
        self.assertGreater(result.distance_km, 3.0)

    def test_mountain_fastest_and_safest_are_different(self) -> None:
        fastest = calculate_route(self.mountain_request(cost_mode="travel_time"))
        safest = calculate_route(
            self.mountain_request(
                algorithm="risk_aware_astar",
                cost_mode="travel_time",
                risk_weight=20.0,
            )
        )

        self.assertNotEqual(fastest.route_edges, safest.route_edges)
        self.assertGreater(safest.estimated_travel_time_minutes, fastest.estimated_travel_time_minutes)
        self.assertLess(safest.metadata["risk_exposure"], fastest.metadata["risk_exposure"])

    def test_slope_affects_eta(self) -> None:
        gentle = RoadEdge(
            "edge_gentle",
            "start",
            "goal",
            length_km=1.0,
            speed_kmh=30.0,
            slope_percent=3.0,
            road_class="secondary_road",
            surface_type="asphalt",
            road_width_m=5.5,
        )
        steep = replace(gentle, edge_id="edge_steep", slope_percent=15.0)

        self.assertGreater(self.single_edge_eta(steep), self.single_edge_eta(gentle))

    def test_road_condition_affects_eta(self) -> None:
        paved = RoadEdge(
            "edge_paved",
            "start",
            "goal",
            length_km=1.0,
            speed_kmh=30.0,
            slope_percent=3.0,
            road_class="secondary_road",
            surface_type="asphalt",
            road_width_m=5.5,
        )
        dirt = replace(
            paved,
            edge_id="edge_dirt",
            road_class="forest_road",
            surface_type="dirt",
            road_width_m=3.0,
        )

        self.assertGreater(self.single_edge_eta(dirt), self.single_edge_eta(paved))

    def test_fire_engine_marks_trail_as_vehicle_inaccessible(self) -> None:
        result = calculate_route(self.mountain_request(cost_mode="distance"))

        self.assertTrue(result.success)
        self.assertNotIn("edge_narrow_trail_1", result.route_edges)
        self.assertIn("edge_narrow_trail_1", result.accessibility["inaccessible_edges_avoided"])
        self.assertIn("edge_narrow_trail_1", result.accessibility["inaccessible_reasons"])
        self.assertTrue(any("Vehicle-inaccessible" in warning for warning in result.warnings))

    def test_light_vehicle_can_use_trail_that_fire_engine_cannot(self) -> None:
        result = calculate_route(
            self.mountain_request(
                cost_mode="distance",
                vehicle_profile=light_utility_vehicle_profile(),
            )
        )

        self.assert_route_edges(result, ["edge_narrow_trail_1", "edge_narrow_trail_2"])
        self.assertAlmostEqual(0.7, result.distance_km)

    def test_blocked_paved_route_reroutes_fastest_to_fire_access_detour(self) -> None:
        blocked_edges = tuple(
            replace(edge, status="blocked") if edge.edge_id == "edge_paved_fast_1" else edge
            for edge in self.mountain_network.edges.values()
        )
        network = RoadNetwork(nodes=list(self.mountain_network.nodes.values()), edges=list(blocked_edges))

        result = calculate_route(self.mountain_request(cost_mode="travel_time", network=network))

        self.assert_route_edges(result, ["edge_safe_detour_1", "edge_safe_detour_2", "edge_safe_detour_3"])
        self.assertTrue(any("Blocked edges skipped" in warning for warning in result.warnings))

    def test_mountain_unreachable_distinguishes_blocked_from_inaccessible(self) -> None:
        blocked_edges = tuple(
            replace(edge, status="blocked")
            if edge.edge_id in {"edge_mountain_short_1", "edge_paved_fast_1", "edge_safe_detour_1"}
            else edge
            for edge in self.mountain_network.edges.values()
        )
        network = RoadNetwork(nodes=list(self.mountain_network.nodes.values()), edges=list(blocked_edges))

        result = calculate_route(self.mountain_request(network=network))

        self.assertFalse(result.success)
        self.assertTrue(any("Blocked edges skipped" in warning for warning in result.warnings))
        self.assertTrue(any("Vehicle-inaccessible" in warning for warning in result.warnings))
        self.assertIn("edge_narrow_trail_1", result.accessibility["inaccessible_edges_avoided"])

    def test_mountain_geojson_linestring_uses_path_coordinates(self) -> None:
        result = calculate_route(self.mountain_request(cost_mode="travel_time"))

        self.assertEqual("LineString", result.geometry["type"])
        self.assertEqual(
            [
                [self.mountain_network.node(node_id).longitude, self.mountain_network.node(node_id).latitude]
                for node_id in result.route_nodes
            ],
            result.geometry["coordinates"],
        )


if __name__ == "__main__":
    unittest.main()