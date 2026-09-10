from __future__ import annotations

from app.services.routing.models import RoadEdge, RoadNetwork, RoadNode


def build_risk_tradeoff_network() -> RoadNetwork:
    """Small deterministic network where short and safe routes diverge."""
    nodes = [
        RoadNode("start", longitude=101.0000, latitude=28.0000),
        RoadNode("danger_mid", longitude=101.0100, latitude=28.0000),
        RoadNode("goal", longitude=101.0200, latitude=28.0000),
        RoadNode("safe_west", longitude=101.0000, latitude=28.0100),
        RoadNode("safe_east", longitude=101.0100, latitude=28.0100),
    ]
    edges = [
        RoadEdge("edge_short_1", "start", "danger_mid", speed_kmh=40.0, risk_score=0.90),
        RoadEdge("edge_short_2", "danger_mid", "goal", speed_kmh=40.0, risk_score=0.85),
        RoadEdge("edge_safe_1", "start", "safe_west", speed_kmh=35.0, risk_score=0.05),
        RoadEdge("edge_safe_2", "safe_west", "safe_east", speed_kmh=35.0, risk_score=0.05),
        RoadEdge("edge_safe_3", "safe_east", "goal", speed_kmh=35.0, risk_score=0.08),
    ]
    return RoadNetwork(nodes=nodes, edges=edges)


def build_mountain_fire_rescue_network() -> RoadNetwork:
    """Mountain rescue network with short, fast, safe, and vehicle-limited options.

    Route A: short forest road, steep, narrow, dirt, high fire risk.
    Route B: longer paved secondary road, gentler grade, fastest, medium fire risk.
    Route C: longest fire-access detour, stable gravel road, lowest fire risk.
    Narrow cut: very short trail that a fire engine cannot use.
    """
    nodes = [
        RoadNode("base", longitude=101.0000, latitude=28.0000),
        RoadNode("steep_forest", longitude=101.0060, latitude=28.0010),
        RoadNode("incident", longitude=101.0120, latitude=28.0000),
        RoadNode("paved_mid", longitude=101.0060, latitude=28.0060),
        RoadNode("safe_valley", longitude=101.0000, latitude=28.0100),
        RoadNode("safe_ridge", longitude=101.0060, latitude=28.0120),
        RoadNode("narrow_cut", longitude=101.0030, latitude=28.0003),
    ]
    edges = [
        RoadEdge(
            "edge_mountain_short_1",
            "base",
            "steep_forest",
            length_km=1.0,
            speed_kmh=30.0,
            slope_percent=14.0,
            road_class="forest_road",
            surface_type="dirt",
            road_width_m=3.0,
            risk_score=0.75,
        ),
        RoadEdge(
            "edge_mountain_short_2",
            "steep_forest",
            "incident",
            length_km=1.0,
            speed_kmh=28.0,
            slope_percent=12.0,
            road_class="forest_road",
            surface_type="dirt",
            road_width_m=3.0,
            risk_score=0.70,
        ),
        RoadEdge(
            "edge_paved_fast_1",
            "base",
            "paved_mid",
            length_km=1.5,
            speed_kmh=52.0,
            slope_percent=3.0,
            road_class="secondary_road",
            surface_type="asphalt",
            road_width_m=5.6,
            risk_score=0.42,
        ),
        RoadEdge(
            "edge_paved_fast_2",
            "paved_mid",
            "incident",
            length_km=1.5,
            speed_kmh=52.0,
            slope_percent=2.5,
            road_class="secondary_road",
            surface_type="asphalt",
            road_width_m=5.6,
            risk_score=0.40,
        ),
        RoadEdge(
            "edge_safe_detour_1",
            "base",
            "safe_valley",
            length_km=1.4,
            speed_kmh=38.0,
            slope_percent=4.0,
            road_class="fire_access_road",
            surface_type="gravel",
            road_width_m=4.4,
            risk_score=0.08,
        ),
        RoadEdge(
            "edge_safe_detour_2",
            "safe_valley",
            "safe_ridge",
            length_km=1.4,
            speed_kmh=36.0,
            slope_percent=3.5,
            road_class="fire_access_road",
            surface_type="gravel",
            road_width_m=4.2,
            risk_score=0.06,
        ),
        RoadEdge(
            "edge_safe_detour_3",
            "safe_ridge",
            "incident",
            length_km=1.4,
            speed_kmh=36.0,
            slope_percent=3.0,
            road_class="fire_access_road",
            surface_type="gravel",
            road_width_m=4.2,
            risk_score=0.05,
        ),
        RoadEdge(
            "edge_narrow_trail_1",
            "base",
            "narrow_cut",
            length_km=0.35,
            speed_kmh=18.0,
            slope_percent=6.0,
            road_class="trail",
            surface_type="dirt",
            road_width_m=2.3,
            risk_score=0.03,
        ),
        RoadEdge(
            "edge_narrow_trail_2",
            "narrow_cut",
            "incident",
            length_km=0.35,
            speed_kmh=18.0,
            slope_percent=6.0,
            road_class="trail",
            surface_type="dirt",
            road_width_m=2.3,
            risk_score=0.02,
        ),
    ]
    return RoadNetwork(nodes=nodes, edges=edges)