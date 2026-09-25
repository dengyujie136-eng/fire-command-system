import asyncio

from app.llm.providers import LLMResult
from app.routers.planning_preview import (
    MapPoint,
    PreviewRequest,
    RouteExplanationRequest,
    _candidate_route,
    _route_evidence,
    explain_route,
    preview,
)
from app.services.routing import RoadEdge, RoadNetwork, RoadNode


def test_preview_routes_around_large_fire_radius() -> None:
    request = PreviewRequest(
        event_id="route-preview-test",
        fire_center=MapPoint(longitude=-121.38, latitude=39.87),
        fire_radius_km=6.0,
        teams=[
            MapPoint(longitude=-121.38, latitude=39.955),
            MapPoint(longitude=-121.275, latitude=39.87),
        ],
        targets=[
            MapPoint(longitude=-121.38, latitude=39.945),
            MapPoint(longitude=-121.285, latitude=39.87),
        ],
    )

    result = asyncio.run(preview(request))

    assert len(result["plans"]) == 2
    assert result["unassigned_target_indices"] == []
    for plan in result["plans"]:
        route = plan["route"]
        assert route["success"] is True
        assert len(route["geometry"]["coordinates"]) >= 2


def test_preview_uses_irregular_perimeter_instead_of_enclosing_radius() -> None:
    request = PreviewRequest(
        event_id="irregular-fire-preview",
        fire_center=MapPoint(longitude=-121.38, latitude=39.87),
        fire_radius_km=8.0,
        fire_perimeter=[
            MapPoint(longitude=-121.395, latitude=39.86),
            MapPoint(longitude=-121.36, latitude=39.865),
            MapPoint(longitude=-121.365, latitude=39.885),
            MapPoint(longitude=-121.39, latitude=39.88),
            MapPoint(longitude=-121.395, latitude=39.86),
        ],
        teams=[MapPoint(longitude=-121.45, latitude=39.91)],
        # This target is inside the enclosing 8 km radius but outside the actual fire polygon.
        targets=[MapPoint(longitude=-121.42, latitude=39.89)],
    )

    result = asyncio.run(preview(request))

    assert result["plans"][0]["route"]["success"] is True
    assert result["plans"][0]["route"]["algorithm"] == "astar"
    assert len(result["plans"][0]["route"]["geometry"]["coordinates"]) == 2


def test_preview_assigns_extra_teams_as_reinforcements() -> None:
    request = PreviewRequest(
        event_id="all-teams-assigned",
        teams=[
            MapPoint(longitude=-121.45, latitude=39.91),
            MapPoint(longitude=-121.44, latitude=39.90),
            MapPoint(longitude=-121.31, latitude=39.91),
            MapPoint(longitude=-121.30, latitude=39.90),
        ],
        targets=[
            MapPoint(longitude=-121.42, latitude=39.89),
            MapPoint(longitude=-121.33, latitude=39.89),
        ],
    )

    result = asyncio.run(preview(request))

    assert len(result["plans"]) == 4
    assert result["reserve_team_indices"] == []
    assert {plan["team_index"] for plan in result["plans"]} == {0, 1, 2, 3}
    assert sum(plan["assignment_role"] == "primary" for plan in result["plans"]) == 2
    assert sum(plan["assignment_role"] == "reinforcement" for plan in result["plans"]) == 2


def test_preview_uses_global_route_cost_instead_of_target_order_greedy() -> None:
    request = PreviewRequest(
        event_id="global-assignment",
        teams=[
            MapPoint(longitude=-121.40, latitude=39.91),
            MapPoint(longitude=-121.36, latitude=39.91),
        ],
        targets=[
            # Target 1 is centered and would claim team 1 first under the old greedy loop.
            MapPoint(longitude=-121.38, latitude=39.87),
            MapPoint(longitude=-121.40, latitude=39.87),
        ],
    )

    result = asyncio.run(preview(request))
    assignments = {
        plan["team_index"]: plan["target_index"]
        for plan in result["plans"]
        if plan["assignment_role"] == "primary"
    }

    assert result["assignment_method"] == "global_routed_eta_with_crossing_penalty"
    assert assignments == {0: 1, 1: 0}
    assert all(plan["route"]["metadata"]["cost_mode"] == "travel_time" for plan in result["plans"])


def test_candidate_route_falls_back_to_dismounted_crew_for_steep_dem() -> None:
    network = RoadNetwork(
        nodes=[
            RoadNode("team-0", -121.40, 39.90, metadata={"elevation_m": 1000}),
            RoadNode("target-0", -121.399, 39.90, metadata={"elevation_m": 1030}),
        ],
        edges=[
            RoadEdge(
                "steep-approach",
                "team-0",
                "target-0",
                length_km=0.1,
                speed_kmh=12,
                elevation_gain_m=30,
                road_class="fire_access_road",
                surface_type="dirt",
                road_width_m=5,
            )
        ],
    )
    request = PreviewRequest(
        event_id="dixie_fire_2021",
        teams=[MapPoint(longitude=-121.40, latitude=39.90)],
        targets=[MapPoint(longitude=-121.399, latitude=39.90)],
    )

    route = _candidate_route(network, request, 0, 0)

    assert route.success is True
    assert route.metadata["vehicle_type"] == "dismounted_fire_crew"
    assert route.metadata["source"] == "dem_terrain_grid_dismounted_approach"


def test_candidate_route_rejects_excessive_vehicle_detour() -> None:
    nodes = [
        RoadNode("team-0", 0.0, 0.0, metadata={"elevation_m": 0}),
        RoadNode("target-0", 0.01, 0.0, metadata={"elevation_m": 0}),
        RoadNode("north-west", 0.0, 0.02, metadata={"elevation_m": 0}),
        RoadNode("north-east", 0.01, 0.02, metadata={"elevation_m": 0}),
    ]
    edges = [
        RoadEdge(
            "steep-shortcut",
            "team-0",
            "target-0",
            length_km=1.0,
            speed_kmh=12,
            elevation_gain_m=300,
            road_class="fire_access_road",
            surface_type="dirt",
            road_width_m=5,
        ),
        RoadEdge("detour-west", "team-0", "north-west", length_km=2.2, speed_kmh=18, road_class="fire_access_road", surface_type="dirt", road_width_m=5),
        RoadEdge("detour-north", "north-west", "north-east", length_km=1.0, speed_kmh=18, road_class="fire_access_road", surface_type="dirt", road_width_m=5),
        RoadEdge("detour-east", "north-east", "target-0", length_km=2.2, speed_kmh=18, road_class="fire_access_road", surface_type="dirt", road_width_m=5),
    ]
    request = PreviewRequest(
        event_id="dixie_fire_2021",
        teams=[MapPoint(longitude=0.0, latitude=0.0)],
        targets=[MapPoint(longitude=0.01, latitude=0.0)],
    )

    route = _candidate_route(RoadNetwork(nodes, edges), request, 0, 0)

    assert route.success is True
    assert route.metadata["vehicle_type"] == "dismounted_fire_crew"
    assert route.route_edges == ["steep-shortcut"]


def test_route_evidence_distinguishes_fire_detour_from_grid_approximation() -> None:
    request = RouteExplanationRequest(
        event_id="route-explanation",
        team_index=0,
        target_index=0,
        team=MapPoint(longitude=-121.42, latitude=39.87),
        target=MapPoint(longitude=-121.34, latitude=39.87),
        fire_perimeter=[
            MapPoint(longitude=-121.39, latitude=39.85),
            MapPoint(longitude=-121.37, latitude=39.85),
            MapPoint(longitude=-121.37, latitude=39.89),
            MapPoint(longitude=-121.39, latitude=39.89),
        ],
        route={
            "success": True,
            "distance_km": 9.5,
            "geometry": {"coordinates": [[-121.42, 39.87], [-121.38, 39.84], [-121.34, 39.87]]},
        },
    )

    evidence = _route_evidence(request)

    assert evidence["direct_segment_crosses_fire_perimeter"] is True
    assert evidence["reason_code"] == "fire_perimeter_avoidance"
    assert evidence["detour_ratio"] > 1


def test_route_evidence_identifies_dem_terrain_constraint() -> None:
    request = RouteExplanationRequest(
        event_id="dixie_fire_2021",
        team_index=0,
        target_index=0,
        team=MapPoint(longitude=-121.45, latitude=39.91),
        target=MapPoint(longitude=-121.42, latitude=39.89),
        route={
            "success": True,
            "distance_km": 3.64,
            "metadata": {"source": "dem_terrain_grid_no_verified_roads"},
            "terrain_metrics": {
                "elevation_gain_m": 51.4,
                "elevation_loss_m": 43.3,
                "max_slope_percent": 14.95,
                "average_slope_percent": 2.6,
            },
            "geometry": {
                "coordinates": [
                    [-121.45, 39.91],
                    [-121.44, 39.90],
                    [-121.42, 39.89],
                ]
            },
        },
    )

    evidence = _route_evidence(request)

    assert evidence["terrain_aware"] is True
    assert evidence["reason_code"] == "terrain_constrained_grid_route"
    assert evidence["terrain_metrics"]["max_slope_percent"] == 14.95


def test_explain_route_reports_real_qwen_usage(monkeypatch) -> None:
    class FakeQwen:
        provider_name = "qwen"
        model = "qwen-plus-test"

        async def generate(self, system_prompt, user_payload):
            assert user_payload["evidence"]["reason_code"] == "direct_route_available"
            return LLMResult("qwen", self.model, "直线未穿越火线，因此使用直达路线。", True)

    monkeypatch.setattr("app.routers.planning_preview.get_llm_provider", lambda force_provider=None: FakeQwen())
    request = RouteExplanationRequest(
        event_id="qwen-route-explanation",
        team_index=0,
        target_index=0,
        team=MapPoint(longitude=-121.42, latitude=39.87),
        target=MapPoint(longitude=-121.40, latitude=39.87),
        route={
            "success": True,
            "distance_km": 1.7,
            "geometry": {"coordinates": [[-121.42, 39.87], [-121.40, 39.87]]},
        },
    )

    result = asyncio.run(explain_route(request))

    assert result["used_remote"] is True
    assert result["source_mode"] == "qwen_remote"
    assert result["model"] == "qwen-plus-test"
