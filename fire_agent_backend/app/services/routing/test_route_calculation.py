from __future__ import annotations

import math
import unittest
from dataclasses import replace

from app.services.routing import build_risk_tradeoff_network, calculate_route, compare_route_algorithms
from app.services.routing.models import RoutingRequest


class RouteCalculationUnitTest(unittest.TestCase):
    def setUp(self) -> None:
        self.network = build_risk_tradeoff_network()

    def request(self, **overrides: object) -> RoutingRequest:
        base = RoutingRequest(
            network=self.network,
            start_node_id="start",
            destination_node_id="goal",
            metadata={"source": "synthetic_unit_test_network"},
        )
        return replace(base, **overrides)

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


if __name__ == "__main__":
    unittest.main()