from __future__ import annotations

import heapq
import math
from dataclasses import replace
from itertools import count
from typing import Iterable

from app.services.routing.models import (
    RoadEdge,
    RoadNetwork,
    RoadNode,
    RouteResult,
    RoutingAlgorithm,
    RoutingRequest,
    VehicleProfile,
    default_fire_engine_profile,
)

DEFAULT_SPEED_KMH = 30.0
RESTRICTED_EDGE_MULTIPLIER = 1.75
CURVATURE_MAX_PENALTY = 0.35


def calculate_route(request: RoutingRequest) -> RouteResult:
    if request.algorithm == "dijkstra":
        return _search(request, use_heuristic=False, use_risk=False)
    if request.algorithm == "astar":
        return _search(request, use_heuristic=True, use_risk=False)
    if request.algorithm == "risk_aware_astar":
        return _search(request, use_heuristic=True, use_risk=True)
    raise ValueError(f"Unsupported routing algorithm: {request.algorithm}")


def compare_route_algorithms(
    request: RoutingRequest,
    algorithms: Iterable[RoutingAlgorithm] = ("dijkstra", "astar", "risk_aware_astar"),
) -> list[RouteResult]:
    return [calculate_route(replace(request, algorithm=algorithm)) for algorithm in algorithms]


def _search(request: RoutingRequest, *, use_heuristic: bool, use_risk: bool) -> RouteResult:
    network = request.network
    start_node = network.node(request.start_node_id)
    destination_node = network.node(request.destination_node_id)
    blocked_seen: set[str] = set()
    inaccessible_seen: dict[str, str] = {}

    if request.start_node_id == request.destination_node_id:
        return _build_result(
            request=request,
            route_nodes=[request.start_node_id],
            route_edges=[],
            total_cost=0.0,
            blocked_seen=blocked_seen,
            inaccessible_seen=inaccessible_seen,
            visited_count=1,
        )

    open_heap: list[tuple[float, int, str]] = []
    sequence = count()
    g_score: dict[str, float] = {request.start_node_id: 0.0}
    came_from: dict[str, tuple[str, str]] = {}
    visited: set[str] = set()

    heapq.heappush(open_heap, (0.0, next(sequence), request.start_node_id))

    while open_heap:
        _, _, current_id = heapq.heappop(open_heap)
        if current_id in visited:
            continue
        visited.add(current_id)
        if current_id == request.destination_node_id:
            route_nodes, route_edges = _reconstruct_path(came_from, request.start_node_id, current_id)
            return _build_result(
                request=request,
                route_nodes=route_nodes,
                route_edges=route_edges,
                total_cost=g_score[current_id],
                blocked_seen=blocked_seen,
                inaccessible_seen=inaccessible_seen,
                visited_count=len(visited),
            )

        for neighbor_id, edge in network.neighbors(current_id):
            edge_cost = _edge_cost(
                edge,
                request,
                from_node_id=current_id,
                use_risk=use_risk,
                blocked_seen=blocked_seen,
                inaccessible_seen=inaccessible_seen,
            )
            if edge_cost is None:
                continue
            tentative = g_score[current_id] + edge_cost
            if tentative >= g_score.get(neighbor_id, math.inf):
                continue
            came_from[neighbor_id] = (current_id, edge.edge_id)
            g_score[neighbor_id] = tentative
            priority = tentative
            if use_heuristic:
                priority += _heuristic(network.node(neighbor_id), destination_node, request)
            heapq.heappush(open_heap, (priority, next(sequence), neighbor_id))

    return _unreachable_result(
        request,
        blocked_seen=blocked_seen,
        inaccessible_seen=inaccessible_seen,
        visited_count=len(visited),
    )


def _edge_cost(
    edge: RoadEdge,
    request: RoutingRequest,
    *,
    from_node_id: str,
    use_risk: bool,
    blocked_seen: set[str],
    inaccessible_seen: dict[str, str],
) -> float | None:
    status = request.edge_status_overrides.get(edge.edge_id, edge.status)
    if edge.edge_id in request.blocked_edge_ids or status == "blocked":
        blocked_seen.add(edge.edge_id)
        return None

    accessible, reason = _vehicle_accessibility(edge, request, from_node_id)
    if not accessible:
        inaccessible_seen[edge.edge_id] = reason
        return None

    movement_cost = _movement_cost(edge, request, from_node_id=from_node_id)
    if status == "restricted":
        movement_cost *= RESTRICTED_EDGE_MULTIPLIER

    base_cost = max(0.0, float(edge.base_cost or 0.0))
    if not use_risk:
        return movement_cost + base_cost

    risk_score = _edge_risk_score(edge, request)
    risk_weight = max(0.0, float(request.risk_weight))
    risk_penalty = movement_cost * risk_score * risk_weight
    return movement_cost + base_cost + risk_penalty


def _movement_cost(edge: RoadEdge, request: RoutingRequest, *, from_node_id: str) -> float:
    if request.cost_mode == "travel_time":
        return _edge_travel_time_minutes(edge, request.network, request, from_node_id=from_node_id)
    if request.cost_mode == "distance":
        return _edge_length_km(edge, request.network)
    raise ValueError(f"Unsupported routing cost mode: {request.cost_mode}")


def _edge_length_km(edge: RoadEdge, network: RoadNetwork) -> float:
    if edge.length_km is not None:
        return max(0.0, float(edge.length_km))
    start = network.node(edge.from_node_id)
    end = network.node(edge.to_node_id)
    return _haversine_km(start.longitude, start.latitude, end.longitude, end.latitude)


def _edge_travel_time_minutes(
    edge: RoadEdge,
    network: RoadNetwork,
    request: RoutingRequest,
    *,
    from_node_id: str,
) -> float:
    speed = _effective_speed_kmh(edge, network, request, from_node_id=from_node_id)
    length_km = _edge_length_km(edge, network)
    return (length_km / speed) * 60.0


def _effective_speed_kmh(
    edge: RoadEdge,
    network: RoadNetwork,
    request: RoutingRequest,
    *,
    from_node_id: str,
) -> float:
    profile = _vehicle_profile(request)
    nominal_speed = edge.speed_kmh or DEFAULT_SPEED_KMH
    if nominal_speed <= 0:
        nominal_speed = DEFAULT_SPEED_KMH

    slope = _traversal_slope_percent(edge, network, from_node_id=from_node_id)
    if slope >= 0:
        slope_factor = max(0.35, 1.0 - slope * 0.035)
    else:
        slope_factor = max(0.65, 1.0 - abs(slope) * 0.012)

    class_factor = profile.road_class_speed_factors.get(edge.road_class, profile.road_class_speed_factors.get("unknown", 0.70))
    surface_factor = profile.surface_speed_factors.get(edge.surface_type, profile.surface_speed_factors.get("unknown", 0.76))
    width_factor = _width_speed_factor(edge, profile)
    curvature_factor = max(1.0 - min(max(edge.curvature_severity, 0.0), 1.0) * CURVATURE_MAX_PENALTY, 0.65)

    speed = nominal_speed * slope_factor * class_factor * surface_factor * width_factor * curvature_factor
    return max(profile.minimum_speed_kmh, speed)


def _vehicle_accessibility(edge: RoadEdge, request: RoutingRequest, from_node_id: str) -> tuple[bool, str]:
    profile = _vehicle_profile(request)
    if edge.road_class not in profile.allowed_road_classes:
        return False, f"{profile.vehicle_type} is not allowed on road_class={edge.road_class}"
    if edge.road_width_m is not None and edge.road_width_m < profile.minimum_road_width_m:
        return False, (
            f"road_width_m={edge.road_width_m:.2f} is below "
            f"{profile.vehicle_type} minimum {profile.minimum_road_width_m:.2f}"
        )
    slope = abs(_traversal_slope_percent(edge, request.network, from_node_id=from_node_id))
    if slope > profile.max_slope_percent:
        return False, f"slope_percent={slope:.1f} exceeds {profile.vehicle_type} limit {profile.max_slope_percent:.1f}"
    return True, "accessible"


def _width_speed_factor(edge: RoadEdge, profile: VehicleProfile) -> float:
    if edge.road_width_m is None:
        return 0.88
    if edge.road_width_m >= profile.preferred_road_width_m:
        return 1.0
    usable_range = max(profile.preferred_road_width_m - profile.minimum_road_width_m, 0.1)
    position = max(0.0, min(1.0, (edge.road_width_m - profile.minimum_road_width_m) / usable_range))
    return 0.55 + position * 0.45


def _traversal_slope_percent(edge: RoadEdge, network: RoadNetwork, *, from_node_id: str) -> float:
    if edge.elevation_gain_m is not None:
        length_m = max(_edge_length_km(edge, network) * 1000.0, 1.0)
        slope = (edge.elevation_gain_m / length_m) * 100.0
    else:
        slope = float(edge.slope_percent or 0.0)
    if from_node_id == edge.to_node_id:
        return -slope
    return slope


def _edge_risk_score(edge: RoadEdge, request: RoutingRequest) -> float:
    raw = request.edge_risk_overrides.get(edge.edge_id, edge.risk_score)
    return min(1.0, max(0.0, float(raw or 0.0)))


def _heuristic(node: RoadNode, destination: RoadNode, request: RoutingRequest) -> float:
    distance = _haversine_km(node.longitude, node.latitude, destination.longitude, destination.latitude)
    if request.cost_mode == "travel_time":
        return (distance / request.network.max_speed_kmh()) * 60.0
    return distance


def _reconstruct_path(
    came_from: dict[str, tuple[str, str]],
    start_node_id: str,
    destination_node_id: str,
) -> tuple[list[str], list[str]]:
    route_nodes = [destination_node_id]
    route_edges: list[str] = []
    current = destination_node_id
    while current != start_node_id:
        previous, edge_id = came_from[current]
        route_nodes.append(previous)
        route_edges.append(edge_id)
        current = previous
    route_nodes.reverse()
    route_edges.reverse()
    return route_nodes, route_edges


def _build_result(
    *,
    request: RoutingRequest,
    route_nodes: list[str],
    route_edges: list[str],
    total_cost: float,
    blocked_seen: set[str],
    inaccessible_seen: dict[str, str],
    visited_count: int,
) -> RouteResult:
    network = request.network
    profile = _vehicle_profile(request)
    geometry = _geometry_for_nodes(network, route_nodes)
    traversals = list(zip(route_nodes, route_edges, route_nodes[1:]))
    distance = sum(_edge_length_km(network.edge(edge_id), network) for _, edge_id, _ in traversals)
    eta = sum(
        _edge_travel_time_minutes(network.edge(edge_id), network, request, from_node_id=from_node_id)
        for from_node_id, edge_id, _ in traversals
    )
    risk_exposure = sum(
        _edge_length_km(network.edge(edge_id), network) * _edge_risk_score(network.edge(edge_id), request)
        for _, edge_id, _ in traversals
    )
    risk_score = risk_exposure / distance if distance > 0 else 0.0
    risk_cost = sum(
        _movement_cost(network.edge(edge_id), request, from_node_id=from_node_id)
        * _edge_risk_score(network.edge(edge_id), request)
        * max(0.0, request.risk_weight)
        for from_node_id, edge_id, _ in traversals
    )

    warnings = _route_warnings(blocked_seen, inaccessible_seen)

    return RouteResult(
        success=True,
        status="ok",
        algorithm=request.algorithm,
        start=network.node(request.start_node_id).to_point(),
        destination=network.node(request.destination_node_id).to_point(),
        route_nodes=route_nodes,
        route_edges=route_edges,
        geometry=geometry,
        distance_km=round(distance, 4),
        estimated_travel_time_minutes=round(eta, 3),
        risk_cost=round(risk_cost, 4),
        risk_score=round(risk_score, 4),
        total_cost=round(total_cost, 4),
        blocked_edges_avoided=sorted(blocked_seen),
        warnings=warnings,
        metadata={
            "cost_mode": request.cost_mode,
            "risk_weight": request.risk_weight,
            "visited_nodes": visited_count,
            "edge_count": len(route_edges),
            "risk_exposure": round(risk_exposure, 4),
            "source": request.metadata.get("source", "road_network"),
            "vehicle_type": profile.vehicle_type,
        },
        terrain_metrics=_terrain_metrics(network, request, traversals),
        road_metrics=_road_metrics(network, request, traversals),
        accessibility={
            "vehicle_type": profile.vehicle_type,
            "minimum_road_width_m": round(profile.minimum_road_width_m, 3),
            "max_slope_percent": profile.max_slope_percent,
            "inaccessible_edges_avoided": sorted(inaccessible_seen),
            "inaccessible_reasons": dict(sorted(inaccessible_seen.items())),
        },
    )


def _unreachable_result(
    request: RoutingRequest,
    *,
    blocked_seen: set[str],
    inaccessible_seen: dict[str, str],
    visited_count: int,
) -> RouteResult:
    network = request.network
    profile = _vehicle_profile(request)
    configured_blocked = network.blocked_edge_ids(request)
    avoided = sorted(blocked_seen or configured_blocked)
    return RouteResult(
        success=False,
        status="unreachable",
        algorithm=request.algorithm,
        start=network.node(request.start_node_id).to_point(),
        destination=network.node(request.destination_node_id).to_point(),
        route_nodes=[],
        route_edges=[],
        geometry={"type": "LineString", "coordinates": []},
        distance_km=0.0,
        estimated_travel_time_minutes=0.0,
        risk_cost=0.0,
        risk_score=0.0,
        total_cost=math.inf,
        blocked_edges_avoided=avoided,
        warnings=[
            "Destination is unreachable with the current road network, blocked-edge, and vehicle constraints.",
            *_route_warnings(blocked_seen, inaccessible_seen),
        ],
        metadata={
            "cost_mode": request.cost_mode,
            "risk_weight": request.risk_weight,
            "visited_nodes": visited_count,
            "source": request.metadata.get("source", "road_network"),
            "vehicle_type": profile.vehicle_type,
        },
        terrain_metrics={},
        road_metrics={},
        accessibility={
            "vehicle_type": profile.vehicle_type,
            "minimum_road_width_m": round(profile.minimum_road_width_m, 3),
            "max_slope_percent": profile.max_slope_percent,
            "inaccessible_edges_avoided": sorted(inaccessible_seen),
            "inaccessible_reasons": dict(sorted(inaccessible_seen.items())),
        },
    )


def _terrain_metrics(
    network: RoadNetwork,
    request: RoutingRequest,
    traversals: list[tuple[str, str, str]],
) -> dict[str, float]:
    if not traversals:
        return {"elevation_gain_m": 0.0, "elevation_loss_m": 0.0, "max_slope_percent": 0.0, "average_slope_percent": 0.0}
    total_distance = 0.0
    weighted_abs_slope = 0.0
    max_abs_slope = 0.0
    elevation_gain = 0.0
    elevation_loss = 0.0
    for from_node_id, edge_id, _ in traversals:
        edge = network.edge(edge_id)
        length = _edge_length_km(edge, network)
        slope = _traversal_slope_percent(edge, network, from_node_id=from_node_id)
        elevation_delta = (slope / 100.0) * length * 1000.0
        if elevation_delta > 0:
            elevation_gain += elevation_delta
        else:
            elevation_loss += abs(elevation_delta)
        abs_slope = abs(slope)
        total_distance += length
        weighted_abs_slope += abs_slope * length
        max_abs_slope = max(max_abs_slope, abs_slope)
    average = weighted_abs_slope / total_distance if total_distance > 0 else 0.0
    return {
        "elevation_gain_m": round(elevation_gain, 2),
        "elevation_loss_m": round(elevation_loss, 2),
        "max_slope_percent": round(max_abs_slope, 2),
        "average_slope_percent": round(average, 2),
    }


def _road_metrics(
    network: RoadNetwork,
    request: RoutingRequest,
    traversals: list[tuple[str, str, str]],
) -> dict[str, float | int]:
    forest_distance = 0.0
    unpaved_distance = 0.0
    restricted_count = 0
    narrow_count = 0
    profile = _vehicle_profile(request)
    for _, edge_id, _ in traversals:
        edge = network.edge(edge_id)
        length = _edge_length_km(edge, network)
        status = request.edge_status_overrides.get(edge.edge_id, edge.status)
        if edge.road_class == "forest_road":
            forest_distance += length
        if edge.surface_type in {"gravel", "dirt"}:
            unpaved_distance += length
        if status == "restricted":
            restricted_count += 1
        if edge.road_width_m is not None and edge.road_width_m < profile.preferred_road_width_m:
            narrow_count += 1
    return {
        "forest_road_distance_km": round(forest_distance, 4),
        "unpaved_distance_km": round(unpaved_distance, 4),
        "restricted_segment_count": restricted_count,
        "narrow_segment_count": narrow_count,
    }



def _route_warnings(blocked_seen: set[str], inaccessible_seen: dict[str, str]) -> list[str]:
    warnings: list[str] = []
    if blocked_seen:
        warnings.append(f"Blocked edges skipped: {', '.join(sorted(blocked_seen))}.")
    if inaccessible_seen:
        warnings.append(f"Vehicle-inaccessible edges skipped: {', '.join(sorted(inaccessible_seen))}.")
    return warnings


def _geometry_for_nodes(network: RoadNetwork, route_nodes: list[str]) -> dict[str, object]:
    return {
        "type": "LineString",
        "coordinates": [
            [network.node(node_id).longitude, network.node(node_id).latitude]
            for node_id in route_nodes
        ],
    }


def _vehicle_profile(request: RoutingRequest) -> VehicleProfile:
    return request.vehicle_profile or default_fire_engine_profile()


def _haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    radius_km = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    return 2 * radius_km * math.atan2(math.sqrt(a), math.sqrt(1 - a))