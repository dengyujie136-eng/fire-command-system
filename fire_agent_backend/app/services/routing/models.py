from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

RoadStatus = Literal["normal", "restricted", "blocked"]
RoutingAlgorithm = Literal["dijkstra", "astar", "risk_aware_astar"]
RoutingCostMode = Literal["distance", "travel_time"]


@dataclass(frozen=True)
class RoadNode:
    node_id: str
    longitude: float
    latitude: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_point(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "longitude": self.longitude,
            "latitude": self.latitude,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class RoadEdge:
    edge_id: str
    from_node_id: str
    to_node_id: str
    length_km: float | None = None
    speed_kmh: float | None = 30.0
    status: RoadStatus = "normal"
    base_cost: float = 0.0
    risk_score: float = 0.0
    bidirectional: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RoutingRequest:
    network: "RoadNetwork"
    start_node_id: str
    destination_node_id: str
    algorithm: RoutingAlgorithm = "astar"
    cost_mode: RoutingCostMode = "distance"
    risk_weight: float = 0.0
    blocked_edge_ids: frozenset[str] = field(default_factory=frozenset)
    edge_status_overrides: dict[str, RoadStatus] = field(default_factory=dict)
    edge_risk_overrides: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RouteResult:
    success: bool
    status: Literal["ok", "unreachable"]
    algorithm: RoutingAlgorithm
    start: dict[str, Any]
    destination: dict[str, Any]
    route_nodes: list[str]
    route_edges: list[str]
    geometry: dict[str, Any]
    distance_km: float
    estimated_travel_time_minutes: float
    risk_cost: float
    risk_score: float
    total_cost: float
    blocked_edges_avoided: list[str]
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "status": self.status,
            "algorithm": self.algorithm,
            "start": self.start,
            "destination": self.destination,
            "route_nodes": list(self.route_nodes),
            "route_edges": list(self.route_edges),
            "geometry": self.geometry,
            "distance_km": self.distance_km,
            "estimated_travel_time_minutes": self.estimated_travel_time_minutes,
            "risk_cost": self.risk_cost,
            "risk_score": self.risk_score,
            "total_cost": self.total_cost,
            "blocked_edges_avoided": list(self.blocked_edges_avoided),
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }


class RoadNetwork:
    def __init__(self, nodes: list[RoadNode], edges: list[RoadEdge]) -> None:
        self.nodes: dict[str, RoadNode] = {}
        for node in nodes:
            if node.node_id in self.nodes:
                raise ValueError(f"Duplicate road node: {node.node_id}")
            self.nodes[node.node_id] = node

        self.edges: dict[str, RoadEdge] = {}
        self._adjacency: dict[str, list[tuple[str, RoadEdge]]] = {node_id: [] for node_id in self.nodes}
        for edge in edges:
            if edge.edge_id in self.edges:
                raise ValueError(f"Duplicate road edge: {edge.edge_id}")
            if edge.from_node_id not in self.nodes:
                raise ValueError(f"Edge {edge.edge_id} has unknown from node: {edge.from_node_id}")
            if edge.to_node_id not in self.nodes:
                raise ValueError(f"Edge {edge.edge_id} has unknown to node: {edge.to_node_id}")
            self.edges[edge.edge_id] = edge
            self._adjacency[edge.from_node_id].append((edge.to_node_id, edge))
            if edge.bidirectional:
                self._adjacency[edge.to_node_id].append((edge.from_node_id, edge))

    def node(self, node_id: str) -> RoadNode:
        try:
            return self.nodes[node_id]
        except KeyError as exc:
            raise ValueError(f"Unknown road node: {node_id}") from exc

    def edge(self, edge_id: str) -> RoadEdge:
        try:
            return self.edges[edge_id]
        except KeyError as exc:
            raise ValueError(f"Unknown road edge: {edge_id}") from exc

    def neighbors(self, node_id: str) -> list[tuple[str, RoadEdge]]:
        self.node(node_id)
        return list(self._adjacency[node_id])

    def blocked_edge_ids(self, request: RoutingRequest | None = None) -> set[str]:
        blocked = {edge_id for edge_id, edge in self.edges.items() if edge.status == "blocked"}
        if request:
            blocked.update(request.blocked_edge_ids)
            blocked.update(
                edge_id
                for edge_id, status in request.edge_status_overrides.items()
                if status == "blocked"
            )
        return blocked

    def max_speed_kmh(self) -> float:
        speeds = [edge.speed_kmh for edge in self.edges.values() if edge.speed_kmh and edge.speed_kmh > 0]
        return max(speeds) if speeds else 30.0