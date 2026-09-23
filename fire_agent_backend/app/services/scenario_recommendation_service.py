from __future__ import annotations

from hashlib import sha256
from math import asin, cos, radians, sin, sqrt
from typing import Any, Protocol

from app.services.resources import Resource
from app.services.routing import RoadEdge, RoadNetwork, RoadNode, default_fire_engine_profile


# These are intentionally internal exercise rules, not operational fire-service standards.
RULE_VERSION = "scenario-rules-v0.3"
RESOURCE_RULE_VERSION = "resource-rules-v0.4"
ROUTING_RULE_VERSION = "routing-rules-v0.3"


def _stable_number(event_id: str, label: str) -> float:
    digest = sha256(f"{event_id}:{RULE_VERSION}:{label}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / float(2**64 - 1)


def _offset(longitude: float, latitude: float, distance_km: float, bearing_deg: float) -> tuple[float, float]:
    bearing = radians(bearing_deg)
    dlat = distance_km * cos(bearing) / 111.32
    dlng = distance_km * sin(bearing) / max(20.0, 111.32 * cos(radians(latitude)))
    return round(longitude + dlng, 6), round(latitude + dlat, 6)


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lon1, lat1 = map(radians, a)
    lon2, lat2 = map(radians, b)
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    value = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371.0088 * 2 * asin(sqrt(value))


def size_class(final_area_km2: float, risk_level: str) -> str:
    severity = {"low": 0, "medium": 1, "high": 2, "extreme": 3}.get(risk_level.lower(), 1)
    if final_area_km2 >= 200 or severity >= 3:
        return "EXTREME"
    if final_area_km2 >= 50 or severity >= 2:
        return "LARGE"
    if final_area_km2 >= 5:
        return "MEDIUM"
    return "SMALL"


RESOURCE_TEMPLATES: dict[str, dict[str, int]] = {
    "SMALL": {"fire_team": 2, "fire_engine": 2, "medical": 1, "water_supply": 1},
    "MEDIUM": {"fire_team": 4, "fire_engine": 4, "firefighter_unit": 2, "medical": 1, "water_supply": 2},
    "LARGE": {"fire_team": 7, "fire_engine": 7, "firefighter_unit": 4, "medical": 2, "water_supply": 3, "evacuation_support": 2},
    "EXTREME": {"fire_team": 10, "fire_engine": 10, "firefighter_unit": 6, "medical": 3, "water_supply": 5, "evacuation_support": 4, "ground_vehicle": 4},
}


CAPABILITIES: dict[str, list[str]] = {
    "fire_team": ["wildland_suppression", "hand_line"],
    "fire_engine": ["wildland_suppression", "water_delivery"],
    "firefighter_unit": ["wildland_suppression", "structure_protection"],
    "water_supply": ["water_delivery"],
    "medical": ["medical_support"],
    "evacuation_support": ["evacuation_support"],
    "ground_vehicle": ["logistics"],
}


class RoadNetworkProvider(Protocol):
    mode: str

    def build(self, blueprint: dict[str, Any]) -> RoadNetwork: ...


class ScenarioRoadNetworkProvider:
    """Deterministic exercise accessibility graph; never represented as a real road graph."""

    mode = "SCENARIO_ROUTE"

    def build(self, blueprint: dict[str, Any]) -> RoadNetwork:
        points = blueprint["network_points"]
        nodes = [
            RoadNode(
                node_id=item["node_id"],
                longitude=item["longitude"],
                latitude=item["latitude"],
                metadata={"mode": self.mode, "role": item.get("role", "exercise_node")},
            )
            for item in points
        ]
        by_id = {item["node_id"]: item for item in points}
        edges = []
        for index, (left, right, risk) in enumerate(blueprint["network_links"], start=1):
            a = by_id[left]
            b = by_id[right]
            edges.append(
                RoadEdge(
                    edge_id=f"scenario-edge-{index}",
                    from_node_id=left,
                    to_node_id=right,
                    length_km=max(0.05, haversine_km((a["longitude"], a["latitude"]), (b["longitude"], b["latitude"]))),
                    speed_kmh=28.0,
                    risk_score=round(float(risk), 4),
                    metadata={"mode": self.mode, "risk_source": "空间风险等级与火势传播结果"},
                )
            )
        return RoadNetwork(nodes, edges)


class ScenarioRecommendationService:
    """Creates explicitly labelled internal exercise points from current spread outputs."""

    def generate(
        self,
        *,
        event_id: str,
        ignition: tuple[float, float],
        max_radius_km: float,
        final_area_km2: float,
        spread_direction_deg: float,
        risk_level: str,
        mode: str = "RECOMMENDED",
        manual: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        manual = manual or {}
        event_size = size_class(final_area_km2, risk_level)
        fire_edge_radius = max(0.15, float(max_radius_km or 0))
        risk_factor = {"low": 0.08, "medium": 0.16, "high": 0.28, "extreme": 0.42}.get(risk_level.lower(), 0.16)
        safety_margin = max(0.25, min(3.2, fire_edge_radius * (0.18 + risk_factor) + sqrt(max(final_area_km2, 0.01)) * 0.045))
        operations_distance = fire_edge_radius + safety_margin
        staging_distance = operations_distance + max(0.35, min(2.4, fire_edge_radius * 0.36 + safety_margin * 0.75))
        command_distance = staging_distance + max(0.7, min(3.6, fire_edge_radius * 0.55 + safety_margin))
        protected_distance = fire_edge_radius + max(0.35, safety_margin * 0.8)
        safe_bearing = (spread_direction_deg + 180.0) % 360.0
        risk_bearing = spread_direction_deg % 360.0
        missing_data = ["真实 OSM 路网", "已核实资源库存", "候选点实测坡度"]

        command_locations = self._candidate_locations(
            event_id, "command_post", ignition, safe_bearing, command_distance, missing_data, "现场指挥与信息汇总", "位于传播主方向的反侧安全区域"
        )
        staging_locations = self._candidate_locations(
            event_id, "staging_area", ignition, safe_bearing, staging_distance, missing_data, "人员、车辆和补给集结", "兼顾安全边界与接近火场的演练可达性"
        )
        if mode == "MANUAL":
            command_locations = self._manual_or_default(event_id, "command_post", manual.get("command_post"), command_locations[0], "人工设置指挥点")
            staging_locations = self._manual_or_default(event_id, "staging_area", manual.get("staging_area"), staging_locations[0], "人工设置集结区")

        approach_lon, approach_lat = _offset(*ignition, operations_distance, safe_bearing)
        target_lon, target_lat = _offset(*ignition, protected_distance, risk_bearing)
        operation_approach = self._fixed_location(
            event_id, "operations_approach", 1, approach_lon, approach_lat, operations_distance, "exercise",
            "火场作业接近点", "位于当前火场边缘外侧，并避开主要传播方向；用于演练中的灭火队伍作业接近。",
            ["火场边缘来自当前火势推演", "安全余量随预测半径、面积和空间风险等级动态计算"],
            missing_data,
        )
        protected_target = self._fixed_location(
            event_id, "protected_target", 1, target_lon, target_lat, protected_distance, "exercise",
            "演练重点保护目标", "沿模型主要传播方向设置的演练目标，用于呈现潜在受威胁方向，不代表真实居民区或设施。",
            ["目标位置为演练场景生成", "用于评估火势向重点目标方向发展的可能性"],
            missing_data,
        )
        team_locations = self._team_locations(event_id, staging_locations[0], operations_distance, missing_data)
        locations = [*command_locations, *staging_locations, operation_approach, protected_target, *team_locations]
        for value in manual.get("resource_points") or []:
            locations.append(self._manual_location(event_id, "manual_support_point", value, len(locations) + 1, "人工标记保障点"))

        resources = self._resources(event_id, event_size, team_locations)
        waypoint_lon, waypoint_lat = _offset(
            *ignition,
            operations_distance + max(0.18, safety_margin * 0.45),
            safe_bearing + 26,
        )
        network_points = [
            {"node_id": "operations-approach", "longitude": approach_lon, "latitude": approach_lat, "role": "operations_approach"},
            {"node_id": "safe-waypoint", "longitude": waypoint_lon, "latitude": waypoint_lat, "role": "safety_waypoint"},
            {"node_id": "command", "longitude": command_locations[0]["longitude"], "latitude": command_locations[0]["latitude"], "role": "command_post"},
            {"node_id": "staging", "longitude": staging_locations[0]["longitude"], "latitude": staging_locations[0]["latitude"], "role": "staging_area"},
            {"node_id": "protected-target", "longitude": target_lon, "latitude": target_lat, "role": "exercise_protected_target"},
        ]
        for index, team in enumerate(team_locations, start=1):
            network_points.append({"node_id": f"team-{index}", "longitude": team["longitude"], "latitude": team["latitude"], "role": "rescue_team"})
        for item in resources:
            network_points.append({"node_id": item["node_id"], "longitude": item["longitude"], "latitude": item["latitude"], "role": "resource_inventory"})
        route_risk = min(0.88, 0.12 + risk_factor + min(0.28, fire_edge_radius * 0.04))
        network_links: list[tuple[str, str, float]] = [
            ("command", "staging", round(0.08 + risk_factor * 0.2, 3)),
            ("staging", "safe-waypoint", round(0.12 + risk_factor * 0.25, 3)),
            ("safe-waypoint", "operations-approach", round(route_risk, 3)),
            ("team-1", "staging", 0.06),
            ("team-2", "staging", 0.07),
            ("team-3", "staging", 0.08),
            ("operations-approach", "protected-target", min(0.94, round(route_risk + 0.25, 3))),
        ]
        network_links.extend((item["node_id"], item["team_node_id"], 0.05) for item in resources)
        inventory = [
            {"resource_type": item["resource_type"], "total": item["quantity"], "allocated": 0, "remaining": item["quantity"], "status": "available"}
            for item in resources
        ]
        return {
            "mode": mode,
            "rule_version": RULE_VERSION,
            "resource_rule_version": RESOURCE_RULE_VERSION,
            "routing_rule_version": ROUTING_RULE_VERSION,
            "size_class": event_size,
            "ignition": {"longitude": ignition[0], "latitude": ignition[1]},
            "fire_edge_radius_km": round(fire_edge_radius, 3),
            "fire_exclusion_radius_km": round(operations_distance, 3),
            "safety_margin_km": round(safety_margin, 3),
            "spread_direction_deg": round(spread_direction_deg, 1),
            "locations": locations,
            "resources": resources,
            "resource_inventory": inventory,
            "network_points": network_points,
            "network_links": network_links,
            "operations_node_id": "operations-approach",
            "operation_approach_node_id": "operations-approach",
            "command_node_id": "command",
            "staging_node_id": "staging",
            "team_node_ids": ["team-1", "team-2", "team-3"],
            "protected_target_node_id": "protected-target",
            "missing_data": missing_data,
            "limitations": [
                "候选点采用内部演练规则生成，不构成官方消防安全距离或调度标准。",
                "演练可达性路径不是实时道路导航；真实 OSM 路网接入后需重新计算。",
                "演练重点保护目标不是现实居民区或关键设施。",
            ],
            "rescue_situation": {
                "fire_spread_direction_deg": round(spread_direction_deg, 1),
                "fire_edge_radius_km": round(fire_edge_radius, 3),
                "operation_approach": "火场作业接近点位于当前火场边缘外侧的反传播方向。",
                "protected_target": "重点保护目标为演练目标，用于表达模型传播方向上的潜在威胁。",
                "route_risk_source": "空间风险等级与火势预测半径",
            },
        }

    def _candidate_locations(
        self,
        event_id: str,
        location_type: str,
        ignition: tuple[float, float],
        bearing: float,
        base_distance: float,
        missing_data: list[str],
        role: str,
        rationale: str,
    ) -> list[dict[str, Any]]:
        results = []
        for rank in range(1, 4):
            angle = bearing + (rank - 2) * 18 + (_stable_number(event_id, f"{location_type}-{rank}") - 0.5) * 8
            distance = base_distance * (0.92 + rank * 0.1)
            longitude, latitude = _offset(*ignition, distance, angle)
            results.append(
                self._fixed_location(
                    event_id, location_type, rank, longitude, latitude, distance, "recommended", role,
                    rationale,
                    ["位于当前火场边缘外侧", "在模型传播主方向反侧或侧翼", "距离按当前火场尺度动态计算"],
                    missing_data,
                    selected=rank == 1,
                    score=round(max(0.45, 0.95 - rank * 0.07), 3),
                )
            )
        return results

    def _fixed_location(
        self,
        event_id: str,
        location_type: str,
        rank: int,
        longitude: float,
        latitude: float,
        distance_km: float,
        source: str,
        role: str,
        rationale: str,
        evidence: list[str],
        missing_data: list[str],
        *,
        selected: bool = True,
        score: float = 0.82,
    ) -> dict[str, Any]:
        return {
            "location_id": f"loc-{event_id}-{location_type}-{rank}",
            "location_type": location_type,
            "rank": rank,
            "longitude": longitude,
            "latitude": latitude,
            "source": source,
            "selected": selected,
            "score": score,
            "evidence": [{"rule_id": "R-SCN-ROLE", "value": value} for value in evidence] + [{"rule_id": "R-SCN-DIST", "distance_km": round(distance_km, 2)}],
            "reason": [rationale, f"距起火参考点约 {distance_km:.1f} km。"],
            "missing_data": list(missing_data),
            "limitations": ["内部演练点位，需由人工完成现场安全复核。"],
            "metadata": {"role": role, "rule_version": RULE_VERSION},
        }

    def _manual_or_default(
        self,
        event_id: str,
        location_type: str,
        value: Any,
        fallback: dict[str, Any],
        role: str,
    ) -> list[dict[str, Any]]:
        if not value:
            return [fallback]
        longitude, latitude = float(value[0]), float(value[1])
        item = self._manual_location(event_id, location_type, (longitude, latitude), 1, role)
        return [item]

    def _manual_location(self, event_id: str, location_type: str, value: Any, rank: int, role: str) -> dict[str, Any]:
        longitude, latitude = float(value[0]), float(value[1])
        return {
            "location_id": f"loc-{event_id}-{location_type}-manual-{rank}",
            "location_type": location_type,
            "rank": rank,
            "longitude": longitude,
            "latitude": latitude,
            "source": "manual",
            "selected": True,
            "score": 0.0,
            "evidence": [{"rule_id": "R-SCN-MANUAL", "value": "human_selected"}],
            "reason": ["由人工在地图上设置，尚未进行现场安全核验。"],
            "missing_data": ["真实 OSM 路网", "候选点实测坡度"],
            "limitations": ["人工点位必须在实际行动前完成安全复核。"],
            "metadata": {"role": role, "rule_version": RULE_VERSION},
        }

    def _team_locations(
        self,
        event_id: str,
        staging: dict[str, Any],
        operations_distance: float,
        missing_data: list[str],
    ) -> list[dict[str, Any]]:
        teams = []
        for rank in range(1, 4):
            longitude, latitude = _offset(staging["longitude"], staging["latitude"], 0.16 + rank * 0.08, 18 + rank * 46)
            teams.append(
                self._fixed_location(
                    event_id, "rescue_team", rank, longitude, latitude, operations_distance, "exercise",
                    f"演练灭火队伍 {rank}", "演练队伍从资源集结区域部署，用作灭火作业路线的起点。",
                    ["队伍位置由场景引擎确定性生成", "队伍服务于火场作业接近点"], missing_data,
                    selected=rank == 1, score=0.8 - rank * 0.04,
                )
            )
        return teams

    def _resources(self, event_id: str, event_size: str, teams: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for index, (resource_type, quantity) in enumerate(RESOURCE_TEMPLATES[event_size].items(), start=1):
            team_index = (index - 1) % len(teams)
            team = teams[team_index]
            result.append(
                {
                    "resource_id": f"scn-{event_id}-{resource_type}-{index}",
                    "node_id": f"resource-{index}",
                    "team_node_id": f"team-{team_index + 1}",
                    "resource_type": resource_type,
                    "name": f"{resource_type} 库存",
                    "longitude": team["longitude"],
                    "latitude": team["latitude"],
                    "status": "available",
                    "capabilities": CAPABILITIES[resource_type],
                    "capacity": {"units": float(quantity)},
                    "quantity": quantity,
                    "readiness": round(0.82 + _stable_number(event_id, resource_type) * 0.16, 3),
                    "mobility_mode": "static" if resource_type == "water_supply" else "ground",
                    "mode": "SCENARIO",
                    "metadata": {
                        "template": event_size,
                        "rule_version": RESOURCE_RULE_VERSION,
                        "inventory_kind": "exercise_inventory",
                        "display_mode": "inventory",
                    },
                }
            )
        return result


def resources_from_blueprint(blueprint: dict[str, Any]) -> list[Resource]:
    profile = default_fire_engine_profile()
    return [
        Resource(
            resource_id=item["resource_id"],
            resource_type=item["resource_type"],
            name=item["name"],
            location_node_id=item["node_id"],
            longitude=item["longitude"],
            latitude=item["latitude"],
            status=item["status"],
            available=item["status"] == "available",
            capabilities=frozenset(item["capabilities"]),
            capacity=item["capacity"],
            quantity=item["quantity"],
            readiness=item["readiness"],
            mobility_mode=item["mobility_mode"],
            vehicle_profile=profile if item["mobility_mode"] == "ground" else None,
            response_speed_kmh=32.0,
            metadata={**item["metadata"], "mode": "SCENARIO"},
        )
        for item in blueprint["resources"]
    ]
