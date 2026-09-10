from __future__ import annotations

from app.services.routing.models import RoadEdge, RoadNetwork, RoadNode


def build_risk_tradeoff_network() -> RoadNetwork:
    """Small deterministic network where short and safe routes diverge.

    Short route: start -> danger_mid -> goal. It is shorter but has high edge risk.
    Safe route: start -> safe_west -> safe_east -> goal. It is longer but low risk.
    """
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