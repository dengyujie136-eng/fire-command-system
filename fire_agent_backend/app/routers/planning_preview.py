from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.llm.providers import get_llm_provider
from app.services.routing import (
    RoadEdge, RoadNetwork, RoadNode, RouteResult, RoutingRequest, VehicleProfile, calculate_route,
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
    fire_perimeter: list[MapPoint] = Field(default_factory=list, max_length=2000)


class RouteExplanationRequest(BaseModel):
    event_id: str = Field(min_length=1, max_length=160)
    team_index: int = Field(ge=0, le=99)
    target_index: int = Field(ge=0, le=99)
    assignment_role: str = Field(default="primary", pattern="^(primary|reinforcement)$")
    team: MapPoint
    target: MapPoint
    route: dict[str, Any]
    fire_perimeter: list[MapPoint] = Field(default_factory=list, max_length=2000)


def _inside_perimeter(longitude: float, latitude: float, perimeter: list[MapPoint]) -> bool:
    if len(perimeter) < 3:
        return False
    inside = False
    previous = perimeter[-1]
    for current in perimeter:
        if ((current.latitude > latitude) != (previous.latitude > latitude)) and (
            longitude
            < (previous.longitude - current.longitude)
            * (latitude - current.latitude)
            / (previous.latitude - current.latitude)
            + current.longitude
        ):
            inside = not inside
        previous = current
    return inside


def _orientation(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect(
    first_start: tuple[float, float],
    first_end: tuple[float, float],
    second_start: tuple[float, float],
    second_end: tuple[float, float],
) -> bool:
    first = _orientation(first_start, first_end, second_start)
    second = _orientation(first_start, first_end, second_end)
    third = _orientation(second_start, second_end, first_start)
    fourth = _orientation(second_start, second_end, first_end)
    return (first > 0) != (second > 0) and (third > 0) != (fourth > 0)


def _crosses_perimeter(start: RoadNode | MapPoint, end: RoadNode | MapPoint, perimeter: list[MapPoint]) -> bool:
    if len(perimeter) < 3:
        return False
    start_pair = (start.longitude, start.latitude)
    end_pair = (end.longitude, end.latitude)
    if _inside_perimeter(start.longitude, start.latitude, perimeter) or _inside_perimeter(end.longitude, end.latitude, perimeter):
        return True
    previous = perimeter[-1]
    for current in perimeter:
        if _segments_intersect(
            start_pair,
            end_pair,
            (previous.longitude, previous.latitude),
            (current.longitude, current.latitude),
        ):
            return True
        previous = current
    return False


def _route_evidence(request: RouteExplanationRequest) -> dict[str, Any]:
    geometry = request.route.get("geometry") or {}
    route_metadata = request.route.get("metadata") or {}
    terrain_metrics = request.route.get("terrain_metrics") or {}
    coordinates = geometry.get("coordinates") or []
    valid_coordinates = [
        point for point in coordinates
        if isinstance(point, (list, tuple)) and len(point) >= 2
    ]
    direct_distance_km = haversine_km(
        (request.team.longitude, request.team.latitude),
        (request.target.longitude, request.target.latitude),
    )
    route_distance_km = float(request.route.get("distance_km") or 0)
    if route_distance_km <= 0 and len(valid_coordinates) >= 2:
        route_distance_km = sum(
            haversine_km(
                (float(start[0]), float(start[1])),
                (float(end[0]), float(end[1])),
            )
            for start, end in zip(valid_coordinates, valid_coordinates[1:])
        )
    detour_ratio = route_distance_km / direct_distance_km if direct_distance_km > 0 else 1.0
    direct_crosses_fire = _crosses_perimeter(request.team, request.target, request.fire_perimeter)
    network_source = str(
        route_metadata.get("source_mode")
        or route_metadata.get("source")
        or "simulated_grid_no_verified_roads"
    )
    terrain_aware = bool(route_metadata.get("terrain_aware")) or network_source.startswith("dem_terrain")
    if direct_crosses_fire:
        reason_code = "fire_perimeter_avoidance"
    elif terrain_aware and len(valid_coordinates) > 2:
        reason_code = "terrain_constrained_grid_route"
    elif len(valid_coordinates) <= 2 or detour_ratio <= 1.05:
        reason_code = "direct_route_available"
    else:
        reason_code = "synthetic_grid_approximation"
    return {
        "team_number": request.team_index + 1,
        "target_number": request.target_index + 1,
        "assignment_role": request.assignment_role,
        "route_success": bool(request.route.get("success")),
        "algorithm": str(request.route.get("algorithm") or "astar"),
        "network_source": network_source,
        "terrain_aware": terrain_aware,
        "terrain_metrics": {
            "elevation_gain_m": terrain_metrics.get("elevation_gain_m"),
            "elevation_loss_m": terrain_metrics.get("elevation_loss_m"),
            "max_slope_percent": terrain_metrics.get("max_slope_percent"),
            "average_slope_percent": terrain_metrics.get("average_slope_percent"),
        },
        "route_distance_km": round(route_distance_km, 4),
        "direct_distance_km": round(direct_distance_km, 4),
        "detour_ratio": round(detour_ratio, 3),
        "extra_distance_km": round(max(0.0, route_distance_km - direct_distance_km), 4),
        "route_point_count": len(valid_coordinates),
        "direct_segment_crosses_fire_perimeter": direct_crosses_fire,
        "fire_perimeter_available": len(request.fire_perimeter) >= 3,
        "reason_code": reason_code,
        "estimated_travel_time_minutes": request.route.get("estimated_travel_time_minutes"),
        "risk_score": request.route.get("risk_score"),
    }


def _fallback_route_explanation(evidence: dict[str, Any]) -> str:
    ratio_percent = max(0, round((float(evidence["detour_ratio"]) - 1) * 100))
    if evidence["reason_code"] == "fire_perimeter_avoidance":
        reason = "队伍到目标的直线穿过当前推演火线，规划器删除了穿越火场的网格边，因此路线沿火线外围绕行。"
    elif evidence["reason_code"] == "terrain_constrained_grid_route":
        metrics = evidence["terrain_metrics"]
        reason = (
            "路线已使用 Copernicus DEM 高程和坡度成本，并避开超过消防车通行坡度的网格边。"
            f"本路线最大坡度约 {float(metrics.get('max_slope_percent') or 0):.1f}%，"
            f"累计爬升约 {float(metrics.get('elevation_gain_m') or 0):.0f} 米。"
        )
    elif evidence["reason_code"] == "synthetic_grid_approximation":
        reason = "队伍到目标的直线没有穿越当前火线，这次折线主要来自演示网格的连接近似，不是已核实的道路绕行。"
    else:
        reason = "队伍到目标的直线未穿越当前火线，规划结果基本采用直达连接，没有明显的避障绕行。"
    return (
        f"{reason} 当前路线 {evidence['route_distance_km']:.2f} km，直线距离 "
        f"{evidence['direct_distance_km']:.2f} km，约多 {ratio_percent}%。"
        "该结果基于模拟网格，实际出动前仍需核实道路、地形和封控信息。"
    )


def _event_dem_path(event_id: str) -> Path | None:
    safe_event_id = "".join(
        character
        for character in event_id
        if character.isalnum() or character in {"-", "_"}
    )
    if safe_event_id != event_id:
        return None
    dem_dir = get_settings().resolved_data_dir / "processed" / "dem"
    candidates = sorted(dem_dir.glob(f"{safe_event_id}_*dem*.tif"))
    return candidates[0] if candidates else None


def _sample_dem_elevations(
    event_id: str,
    points: list[tuple[str, float, float]],
) -> tuple[dict[str, float], dict[str, Any]]:
    path = _event_dem_path(event_id)
    if path is None:
        return {}, {
            "available": False,
            "source": "unavailable",
            "reason": f"No event DEM found for {event_id}",
        }
    try:
        import rasterio
        from pyproj import Transformer

        with rasterio.open(path) as dataset:
            transformer = Transformer.from_crs("EPSG:4326", dataset.crs, always_xy=True)
            projected = [
                transformer.transform(longitude, latitude)
                for _, longitude, latitude in points
            ]
            elevations: dict[str, float] = {}
            for (point_id, _, _), value in zip(points, dataset.sample(projected, masked=True)):
                sample = value[0]
                if getattr(sample, "mask", False):
                    continue
                elevation = float(sample)
                if math.isfinite(elevation) and elevation != dataset.nodata:
                    elevations[point_id] = elevation
            return elevations, {
                "available": bool(elevations),
                "source": "copernicus_dem_glo30",
                "path": path.relative_to(get_settings().resolved_data_dir).as_posix(),
                "crs": str(dataset.crs),
                "sampled_points": len(elevations),
                "requested_points": len(points),
                "resolution_m": [abs(float(dataset.res[0])), abs(float(dataset.res[1]))],
            }
    except Exception as exc:
        return {}, {
            "available": False,
            "source": "unavailable",
            "reason": f"DEM could not be sampled: {type(exc).__name__}: {exc}",
        }


def _exercise_network(request: PreviewRequest) -> tuple[RoadNetwork, dict[str, Any]]:
    perimeter = request.fire_perimeter
    points = request.teams + request.targets + perimeter
    center_latitude = request.fire_center.latitude if request.fire_center else sum(point.latitude for point in points) / len(points)
    fire_padding_km = 1.5 if perimeter else request.fire_radius_km + 2.5 if request.fire_center and request.fire_radius_km else 1.5
    latitude_padding = max(0.012, fire_padding_km / 111.32)
    longitude_padding = max(
        0.012,
        fire_padding_km / max(20.0, 111.32 * math.cos(math.radians(center_latitude))),
    )
    min_lon = min(point.longitude for point in points) - longitude_padding
    max_lon = max(point.longitude for point in points) + longitude_padding
    min_lat = min(point.latitude for point in points) - latitude_padding
    max_lat = max(point.latitude for point in points) + latitude_padding
    if max_lon - min_lon > 0.8 or max_lat - min_lat > 0.8:
        raise HTTPException(status_code=422, detail="Points must stay within one incident planning area")
    span_km = max(
        (max_lat - min_lat) * 111.32,
        (max_lon - min_lon) * max(20.0, 111.32 * math.cos(math.radians(center_latitude))),
    )
    count = max(21, min(41, math.ceil(span_km / 0.45) + 1))
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
    sample_points = [
        (node.node_id, node.longitude, node.latitude)
        for node in nodes
    ] + [
        (f"{group}-{index}", point.longitude, point.latitude)
        for group, items in (("team", request.teams), ("target", request.targets))
        for index, point in enumerate(items)
    ]
    elevations, terrain = _sample_dem_elevations(request.event_id, sample_points)
    terrain["grid_size"] = [count, count]
    terrain["target_cell_size_km"] = 0.45
    nodes = [
        RoadNode(
            node_id=node.node_id,
            longitude=node.longitude,
            latitude=node.latitude,
            metadata={
                **node.metadata,
                **(
                    {"elevation_m": round(elevations[node.node_id], 2)}
                    if node.node_id in elevations
                    else {}
                ),
            },
        )
        for node in nodes
    ]
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
                if perimeter and _crosses_perimeter(current, other, perimeter):
                    continue
                if fire:
                    distance = haversine_km(
                        ((current.longitude + other.longitude) / 2, (current.latitude + other.latitude) / 2),
                        (fire.longitude, fire.latitude),
                    )
                    if not perimeter and request.fire_radius_km and distance < request.fire_radius_km:
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
                    elevation_gain_m=(
                        elevations[other.node_id] - elevations[current.node_id]
                        if current.node_id in elevations and other.node_id in elevations
                        else None
                    ),
                    metadata={
                        "source_mode": "dem_terrain_grid" if terrain["available"] else "simulated_grid",
                        "real_road": False,
                        "terrain_sampled": current.node_id in elevations and other.node_id in elevations,
                    },
                ))
    for group, items in (("team", request.teams), ("target", request.targets)):
        for index, point in enumerate(items):
            if perimeter and _inside_perimeter(point.longitude, point.latitude, perimeter):
                raise HTTPException(status_code=422, detail=f"{group} point {index + 1} is inside the simulated fire perimeter")
            node_id = f"{group}-{index}"
            node = RoadNode(
                node_id=node_id,
                longitude=point.longitude,
                latitude=point.latitude,
                metadata={
                    **(
                        {"elevation_m": round(elevations[node_id], 2)}
                        if node_id in elevations
                        else {}
                    ),
                },
            )
            candidates = sorted(
                nodes, key=lambda grid: haversine_km(
                    (point.longitude, point.latitude), (grid.longitude, grid.latitude)
                )
            )
            max_connector_slope_percent = 45.0

            def connector_is_accessible(grid: RoadNode) -> bool:
                if _crosses_perimeter(point, grid, perimeter):
                    return False
                if not terrain["available"] or node_id not in elevations or grid.node_id not in elevations:
                    return True
                length_m = max(
                    1.0,
                    haversine_km(
                        (point.longitude, point.latitude),
                        (grid.longitude, grid.latitude),
                    ) * 1000,
                )
                slope_percent = abs(elevations[grid.node_id] - elevations[node_id]) / length_m * 100
                return slope_percent <= max_connector_slope_percent

            accessible_candidates = [grid for grid in candidates if connector_is_accessible(grid)]
            sector_connections: dict[int, RoadNode] = {}
            for grid in accessible_candidates:
                east = (grid.longitude - point.longitude) * math.cos(math.radians(point.latitude))
                north = grid.latitude - point.latitude
                sector = int(((math.atan2(north, east) + math.pi) / (math.pi / 4))) % 8
                sector_connections.setdefault(sector, grid)
            connections = list(sector_connections.values())[:6]
            for grid in accessible_candidates:
                if len(connections) >= 6:
                    break
                if grid not in connections:
                    connections.append(grid)
            if not connections:
                raise HTTPException(status_code=422, detail=f"{group} point {index + 1} cannot connect around the simulated fire perimeter")
            nodes.append(node)
            for connector_index, closest in enumerate(connections):
                edges.append(RoadEdge(
                    edge_id=f"connector-{node_id}-{connector_index}",
                    from_node_id=node_id,
                    to_node_id=closest.node_id,
                    speed_kmh=18,
                    road_class="fire_access_road",
                    surface_type="dirt",
                    road_width_m=5,
                    elevation_gain_m=(
                        elevations[closest.node_id] - elevations[node_id]
                        if node_id in elevations and closest.node_id in elevations
                        else None
                    ),
                    metadata={
                        "source_mode": "dem_terrain_connector" if terrain["available"] else "simulated_connector",
                        "real_road": False,
                        "terrain_sampled": node_id in elevations and closest.node_id in elevations,
                        "connector_rank": connector_index,
                    },
                ))
    if not terrain["available"] and (perimeter or not request.fire_radius_km):
        for team_index, team in enumerate(request.teams):
            for target_index, target in enumerate(request.targets):
                if perimeter and _crosses_perimeter(team, target, perimeter):
                    continue
                edges.append(RoadEdge(
                    edge_id=f"direct-team-{team_index}-target-{target_index}",
                    from_node_id=f"team-{team_index}",
                    to_node_id=f"target-{target_index}",
                    speed_kmh=24,
                    risk_score=0.18,
                    road_class="fire_access_road",
                    surface_type="dirt",
                    road_width_m=5,
                    metadata={"source_mode": "simulated_direct", "real_road": False},
                ))
    return RoadNetwork(nodes, edges), terrain


def _candidate_route(
    network: RoadNetwork,
    request: PreviewRequest,
    team_index: int,
    target_index: int,
) -> RouteResult:
    terrain_available = any(
        "elevation_m" in node.metadata
        for node in network.nodes.values()
    )
    common = {
        "network": network,
        "start_node_id": f"team-{team_index}",
        "destination_node_id": f"target-{target_index}",
        "algorithm": "astar",
        "cost_mode": "travel_time",
        "risk_weight": 0.15,
    }
    vehicle_route = calculate_route(RoutingRequest(
        **common,
        vehicle_profile=default_fire_engine_profile(),
        metadata={
            "source": "dem_terrain_grid_no_verified_roads" if terrain_available else "simulated_grid_no_verified_roads",
            "event_id": request.event_id,
        },
    ))
    direct_distance_km = haversine_km(
        (request.teams[team_index].longitude, request.teams[team_index].latitude),
        (request.targets[target_index].longitude, request.targets[target_index].latitude),
    )
    vehicle_detour_ratio = (
        vehicle_route.distance_km / direct_distance_km
        if vehicle_route.success and direct_distance_km > 0
        else math.inf
    )
    if not terrain_available or (vehicle_route.success and vehicle_detour_ratio <= 1.65):
        return vehicle_route
    dismounted_route = calculate_route(RoutingRequest(
        **common,
        vehicle_profile=VehicleProfile(
            vehicle_type="dismounted_fire_crew",
            width_m=0.8,
            max_slope_percent=45.0,
            allowed_road_classes=frozenset({
                "paved_road",
                "secondary_road",
                "forest_road",
                "fire_access_road",
                "unpaved_road",
                "trail",
                "unknown",
            }),
            road_class_speed_factors={
                "paved_road": 0.22,
                "secondary_road": 0.22,
                "forest_road": 0.20,
                "fire_access_road": 0.20,
                "unpaved_road": 0.18,
                "trail": 0.16,
                "unknown": 0.16,
            },
            surface_speed_factors={
                "asphalt": 1.0,
                "gravel": 0.92,
                "dirt": 0.82,
                "unknown": 0.78,
            },
            preferred_road_width_m=1.2,
            minimum_speed_kmh=3.0,
        ),
        metadata={
            "source": "dem_terrain_grid_dismounted_approach",
            "event_id": request.event_id,
        },
    ))
    if dismounted_route.success:
        return dismounted_route
    return vehicle_route


def _dispatch_cost(route: RouteResult) -> float:
    if not route.success:
        return math.inf
    return float(route.total_cost)


def _direct_assignments_cross(
    request: PreviewRequest,
    first: tuple[int, int],
    second: tuple[int, int],
) -> bool:
    first_team, first_target = first
    second_team, second_target = second
    if first_team == second_team or first_target == second_target:
        return False
    return _segments_intersect(
        (request.teams[first_team].longitude, request.teams[first_team].latitude),
        (request.targets[first_target].longitude, request.targets[first_target].latitude),
        (request.teams[second_team].longitude, request.teams[second_team].latitude),
        (request.targets[second_target].longitude, request.targets[second_target].latitude),
    )


def _assignment_objective(
    request: PreviewRequest,
    assignments: list[tuple[int, int]],
    routes: dict[tuple[int, int], RouteResult],
) -> float:
    route_cost = sum(_dispatch_cost(routes[pair]) for pair in assignments)
    crossing_count = sum(
        _direct_assignments_cross(request, first, second)
        for index, first in enumerate(assignments)
        for second in assignments[index + 1:]
    )
    return route_cost + crossing_count * 12.0


def _primary_assignments(
    request: PreviewRequest,
    routes: dict[tuple[int, int], RouteResult],
) -> list[tuple[int, int]]:
    # Maximize coverage first, then minimize the total routed arrival cost.
    states: dict[int, tuple[float, list[tuple[int, int]]]] = {0: (0.0, [])}
    for team_index in range(len(request.teams)):
        updated = dict(states)
        for target_mask, (cost, assignments) in states.items():
            for target_index in range(len(request.targets)):
                bit = 1 << target_index
                route_cost = _dispatch_cost(routes[(team_index, target_index)])
                if target_mask & bit or not math.isfinite(route_cost):
                    continue
                next_mask = target_mask | bit
                next_cost = cost + route_cost
                current = updated.get(next_mask)
                if current is None or next_cost < current[0]:
                    updated[next_mask] = (
                        next_cost,
                        assignments + [(team_index, target_index)],
                    )
        states = updated
    _, (_, assignments) = max(
        states.items(),
        key=lambda item: (item[0].bit_count(), -item[1][0]),
    )

    # Pair swaps preserve coverage while removing costly crossing dispatches.
    improved = True
    while improved:
        improved = False
        baseline = _assignment_objective(request, assignments, routes)
        for first_index in range(len(assignments)):
            for second_index in range(first_index + 1, len(assignments)):
                first_team, first_target = assignments[first_index]
                second_team, second_target = assignments[second_index]
                swapped_pairs = (
                    (first_team, second_target),
                    (second_team, first_target),
                )
                if any(not routes[pair].success for pair in swapped_pairs):
                    continue
                candidate = list(assignments)
                candidate[first_index], candidate[second_index] = swapped_pairs
                if _assignment_objective(request, candidate, routes) + 1e-6 < baseline:
                    assignments = candidate
                    improved = True
                    break
            if improved:
                break
    return sorted(assignments, key=lambda pair: pair[1])


@router.post("/preview")
async def preview(request: PreviewRequest) -> dict[str, Any]:
    network, terrain = _exercise_network(request)
    plans: list[dict[str, Any]] = []
    routes = {
        (team_index, target_index): _candidate_route(network, request, team_index, target_index)
        for team_index in range(len(request.teams))
        for target_index in range(len(request.targets))
    }
    primary = _primary_assignments(request, routes)
    assigned_teams = {team_index for team_index, _ in primary}
    assigned_targets = {target_index for _, target_index in primary}
    target_loads = {target_index: 0 for target_index in range(len(request.targets))}

    def add_plan(team_index: int, target_index: int, assignment_role: str) -> None:
        result = routes[(team_index, target_index)]
        target_loads[target_index] += 1
        plans.append({
            "team_index": team_index,
            "target_index": target_index,
            "assignment_role": assignment_role,
            "access_mode": (
                "dismounted_approach"
                if result.metadata.get("vehicle_type") == "dismounted_fire_crew"
                else "vehicle"
            ),
            "dispatch_cost_minutes": round(_dispatch_cost(result), 3),
            "route": result.to_dict(),
        })

    for team_index, target_index in primary:
        add_plan(team_index, target_index, "primary")

    for team_index in sorted(set(range(len(request.teams))) - assigned_teams):
        reachable_targets = [
            target_index for target_index in range(len(request.targets))
            if routes[(team_index, target_index)].success
        ]
        if not reachable_targets:
            continue
        target_index = min(
            reachable_targets,
            key=lambda candidate: (
                _dispatch_cost(routes[(team_index, candidate)])
                + target_loads[candidate] * 1.5
                + sum(
                    12.0
                    for plan in plans
                    if _direct_assignments_cross(
                        request,
                        (team_index, candidate),
                        (plan["team_index"], plan["target_index"]),
                    )
                )
            ),
        )
        add_plan(team_index, target_index, "reinforcement")
    planned_teams = {plan["team_index"] for plan in plans}
    unassigned = sorted(set(range(len(request.targets))) - assigned_targets)
    reserves = sorted(set(range(len(request.teams))) - planned_teams)
    return {
        "source_mode": "terrain_assisted_simulated" if terrain["available"] else "simulated",
        "network": "dem_terrain_grid_no_verified_roads" if terrain["available"] else "synthetic_grid_no_verified_roads",
        "terrain": terrain,
        "assignment_method": "global_routed_eta_with_crossing_penalty",
        "event_id": request.event_id,
        "plans": plans,
        "unassigned_target_indices": unassigned,
        "reserve_team_indices": reserves,
        "limitations": [
            (
                "Path uses Copernicus DEM elevation and slope on a terrain grid, but not a verified road network."
                if terrain["available"]
                else "Path is calculated on a synthetic planning grid, not a verified road network."
            ),
            "Edges crossing the model fire perimeter are excluded when fire-front geometry is supplied.",
            "Verified roads, blocked roads, travel restrictions and real inventory are not available.",
        ],
    }


@router.post("/explain-route")
async def explain_route(request: RouteExplanationRequest) -> dict[str, Any]:
    evidence = _route_evidence(request)
    system_prompt = (
        "你是森林火灾应急路径解释助手。请用简洁中文解释这条路线为什么直达或绕行。"
        "只能使用提供的证据，不得虚构道路、坡度、交通管制、影像或现场障碍。"
        "必须区分火线避障与合成网格近似，并明确说明这不是经核实的真实道路导航。"
        "当 evidence.terrain_aware 为真时，可依据 terrain_metrics 解释坡度、爬升和地形绕行。"
        "如果直线没有穿越火线但路线仍明显变长，要明确指出绕行来自网格近似。"
        "输出一段不超过120字的行动解释，不使用标题或项目符号。"
    )
    provider = get_llm_provider(force_provider="qwen")
    provider_error: str | None = None
    try:
        result = await provider.generate(
            system_prompt,
            {
                "task": "explain_planned_route",
                "event_id": request.event_id,
                "evidence": evidence,
            },
        )
        explanation = result.content.strip() if result.used_remote and result.content.strip() else _fallback_route_explanation(evidence)
        used_remote = result.used_remote
        provider_name = result.provider
        model = result.model
    except Exception as exc:
        explanation = _fallback_route_explanation(evidence)
        used_remote = False
        provider_name = getattr(provider, "provider_name", "qwen")
        model = getattr(provider, "model", "unknown")
        provider_error = f"{type(exc).__name__}: {exc}"
    warnings = [
        "Route geometry uses a synthetic planning grid, not a verified road network.",
        "Road closures, terrain passability and live traffic were not provided.",
    ]
    if not used_remote:
        warnings.insert(0, "Qwen remote generation was unavailable; deterministic evidence summary returned.")
    return {
        "explanation": explanation,
        "provider": provider_name,
        "model": model,
        "used_remote": used_remote,
        "source_mode": "qwen_remote" if used_remote else "structured_fallback",
        "evidence": evidence,
        "warnings": warnings,
        "provider_error": provider_error,
    }
