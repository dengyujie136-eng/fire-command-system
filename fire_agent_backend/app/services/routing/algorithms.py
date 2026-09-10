from __future__ import annotations

import heapq
import math
from dataclasses import replace
from itertools import count
from typing import Iterable

from app.services.routing.models import RoadEdge, RoadNetwork, RoadNode, RouteResult, RoutingAlgorithm, RoutingRequest

KM_PER_DEGREE_LAT = 111.32
DEFAULT_SPEED_KMH = 30.0
RESTRICTED_EDGE_MULTIPLIER = 1.75


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

    if request.start_node_id == request.destination_node_id:
        return _build_result(
            request=request,
            route_nodes=[request.start_node_id],
            route_edges=[],
            total_cost=0.0,
            blocked_seen=blocked_seen,
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
                visited_count=len(visited),
            )

        for neighbor_id, edge in network.neighbors(current_id):
            edge_cost = _edge_cost(edge, request, use_risk=use_risk, blocked_seen=blocked_seen)
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

    return _unreachable_result(request, blocked_seen=blocked_seen, visited_count=len(visited))


def _edge_cost(
    edge: RoadEdge,
    request: RoutingRequest,
    *,
    use_risk: bool,
    blocked_seen: set[str],
) -> float | None:
    status = request.edge_status_overrides.get(edge.edge_id, edge.status)
    if edge.edge_id in request.blocked_edge_ids or status == "blocked":
        blocked_seen.add(edge.edge_id)
        return None

    movement_cost = _movement_cost(edge, request)
    if status == "restricted":
        movement_cost *= RESTRICTED_EDGE_MULTIPLIER

    base_cost = max(0.0, float(edge.base_cost or 0.0))
    if not use_risk:
        return movement_cost + base_cost

    risk_score = _edge_risk_score(edge, request)
    risk_weight = max(0.0, float(request.risk_weight))
    risk_penalty = movement_cost * risk_score * risk_weight
    return movement_cost + base_cost + risk_penalty


def _movement_cost(edge: RoadEdge, request: RoutingRequest) -> float:
    if request.cost_mode == "travel_time":
        return _edge_travel_time_minutes(edge, request.network)
    if request.cost_mode == "distance":
        return _edge_length_km(edge, request.network)
    raise ValueError(f"Unsupported routing cost mode: {request.cost_mode}")


def _edge_length_km(edge: RoadEdge, network: RoadNetwork) -> float:
    if edge.length_km is not None:
        return max(0.0, float(edge.length_km))
    start = network.node(edge.from_node_id)
    end = network.node(edge.to_node_id)
    return _haversine_km(start.longitude, start.latitude, end.longitude, end.latitude)


def _edge_travel_time_minutes(edge: RoadEdge, network: RoadNetwork) -> float:
    speed = edge.speed_kmh or DEFAULT_SPEED_KMH
    if speed <= 0:
        speed = DEFAULT_SPEED_KMH
    length_km = _edge_length_km(edge, network)
    return (length_km / speed) * 60.0


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
    visited_count: int,
) -> RouteResult:
    network = request.network
    geometry = _geometry_for_nodes(network, route_nodes)
    distance = sum(_edge_length_km(network.edge(edge_id), network) for edge_id in route_edges)
    eta = sum(_edge_travel_time_minutes(network.edge(edge_id), network) for edge_id in route_edges)
    risk_exposure = sum(
        _edge_length_km(network.edge(edge_id), network) * _edge_risk_score(network.edge(edge_id), request)
        for edge_id in route_edges
    )
    risk_score = risk_exposure / distance if distance > 0 else 0.0
    risk_cost = sum(
        _movement_cost(network.edge(edge_id), request)
        * _edge_risk_score(network.edge(edge_id), request)
        * max(0.0, request.risk_weight)
        for edge_id in route_edges
    )

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
        warnings=[],
        metadata={
            "cost_mode": request.cost_mode,
            "risk_weight": request.risk_weight,
            "visited_nodes": visited_count,
            "edge_count": len(route_edges),
            "risk_exposure": round(risk_exposure, 4),
            "source": request.metadata.get("source", "road_network"),
        },
    )


def _unreachable_result(request: RoutingRequest, *, blocked_seen: set[str], visited_count: int) -> RouteResult:
    network = request.network
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
        warnings=["Destination is unreachable with the current road network and blocked-edge constraints."],
        metadata={
            "cost_mode": request.cost_mode,
            "risk_weight": request.risk_weight,
            "visited_nodes": visited_count,
            "source": request.metadata.get("source", "road_network"),
        },
    )


def _geometry_for_nodes(network: RoadNetwork, route_nodes: list[str]) -> dict[str, object]:
    return {
        "type": "LineString",
        "coordinates": [
            [network.node(node_id).longitude, network.node(node_id).latitude]
            for node_id in route_nodes
        ],
    }


def _haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    radius_km = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    return 2 * radius_km * math.atan2(math.sqrt(a), math.sqrt(1 - a))