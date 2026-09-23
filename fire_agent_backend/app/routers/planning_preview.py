from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.routing import (
    RoadEdge, RoadNetwork, RoadNode, RoutingRequest, calculate_route,
    default_fire_engine_profile,
)
from app.services.scenario_recommendation_service import haversine_km

router = APIRouter(prefix="/planning", tags=["planning"])


class MapPoint(BaseModel):
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)


class PreviewRequest(BaseModel):
    event_id: str = Field(min_length=1, max_length=160)
    teams: list[MapPoint] = Field(min_length=1, max_length=12)
    targets: list[MapPoint] = Field(min_length=1, max_length=12)
    fire_center: MapPoint | None = None
    fire_radius_km: float = Field(default=0, ge=0, le=80)


def _exercise_network(request: PreviewRequest) -> RoadNetwork:
    points = request.teams + request.targets
    min_lon = min(point.longitude for point in points) - 0.012
    max_lon = max(point.longitude for point in points) + 0.012
    min_lat = min(point.latitude for point in points) - 0.012
    max_lat = max(point.latitude for point in points) + 0.012
    if max_lon - min_lon > 0.8 or max_lat - min_lat > 0.8:
        raise HTTPException(status_code=422, detail="Points must stay within one incident planning area")
    count = 13
    nodes: list[RoadNode] = []
    edges: list[RoadEdge] = []
    for row in range(count):
        for col in range(count):
            nodes.append(RoadNode(
                node_id=f"grid-{row}-{col}",
                longitude=min_lon + (max_lon - min_lon) * col / (count - 1),
                latitude=min_lat + (max_lat - min_lat) * row / (count - 1),
                metadata={"source_mode": "simulated_grid"},
            ))
    lookup = {node.node_id: node for node in nodes}
    fire = request.fire_center
    for row in range(count):
        for col in range(count):
            current = lookup[f"grid-{row}-{col}"]
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                rr, cc = row + dr, col + dc
                if rr >= count or cc < 0 or cc >= count:
                    continue
                other = lookup[f"grid-{rr}-{cc}"]
                risk = 0.18
                if fire:
                    distance = haversine_km(
                        ((current.longitude + other.longitude) / 2, (current.latitude + other.latitude) / 2),
                        (fire.longitude, fire.latitude),
                    )
                    if request.fire_radius_km and distance < request.fire_radius_km:
                        continue  # Fire-front area is not an exercise route.
                    risk = min(0.9, 0.16 + 0.65 / (1 + distance / 2))
                edges.append(RoadEdge(
                    edge_id=f"grid-edge-{row}-{col}-{rr}-{cc}",
                    from_node_id=current.node_id,
                    to_node_id=other.node_id,
                    speed_kmh=24,
                    risk_score=risk,
                    road_class="fire_access_road",
                    surface_type="dirt",
                    road_width_m=5,
                    metadata={"source_mode": "simulated_grid", "real_road": False},
                ))
    for group, items in (("team", request.teams), ("target", request.targets)):
        for index, point in enumerate(items):
            node_id = f"{group}-{index}"
            node = RoadNode(node_id=node_id, longitude=point.longitude, latitude=point.latitude)
            closest = min(
                nodes, key=lambda grid: haversine_km(
                    (point.longitude, point.latitude), (grid.longitude, grid.latitude)
                )
            )
            nodes.append(node)
            edges.append(RoadEdge(
                edge_id=f"connector-{node_id}",
                from_node_id=node_id,
                to_node_id=closest.node_id,
                speed_kmh=18,
                road_class="fire_access_road",
                surface_type="dirt",
                road_width_m=5,
                metadata={"source_mode": "simulated_connector", "real_road": False},
            ))
    return RoadNetwork(nodes, edges)


@router.post("/preview")
async def preview(request: PreviewRequest) -> dict[str, Any]:
    network = _exercise_network(request)
    available = set(range(len(request.teams)))
    plans: list[dict[str, Any]] = []
    unassigned: list[int] = []
    for target_index, target in enumerate(request.targets):
        if not available:
            unassigned.append(target_index)
            continue
        team_index = min(
            available,
            key=lambda index: haversine_km(
                (request.teams[index].longitude, request.teams[index].latitude),
                (target.longitude, target.latitude),
            ),
        )
        available.remove(team_index)
        result = calculate_route(RoutingRequest(
            network=network,
            start_node_id=f"team-{team_index}",
            destination_node_id=f"target-{target_index}",
            algorithm="risk_aware_astar",
            cost_mode="distance",
            risk_weight=2.5,
            vehicle_profile=default_fire_engine_profile(),
            metadata={"source_mode": "simulated_grid", "event_id": request.event_id},
        ))
        plans.append({
            "team_index": team_index,
            "target_index": target_index,
            "route": result.to_dict(),
        })
    return {
        "source_mode": "simulated",
        "network": "synthetic_grid_no_verified_roads",
        "event_id": request.event_id,
        "plans": plans,
        "unassigned_target_indices": unassigned,
        "reserve_team_indices": sorted(available),
        "limitations": [
            "Path is calculated on a synthetic planning grid, not a verified road network.",
            "Edges crossing the model fire-radius area are excluded when a spread result is supplied.",
            "Terrain slope, blocked roads, travel restrictions and real inventory are not available.",
        ],
    }
