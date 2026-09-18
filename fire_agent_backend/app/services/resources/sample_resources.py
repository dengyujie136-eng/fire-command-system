"""Synthetic resource inventory for resource dispatch unit tests."""

from __future__ import annotations

from app.services.resources.models import Resource, ResourceRequirement, ResourceTask
from app.services.routing import default_fire_engine_profile, light_utility_vehicle_profile


def build_mountain_resource_inventory() -> list[Resource]:
    return [
        Resource(
            resource_id="engine_alpha_near_steep",
            resource_type="fire_engine",
            name="Near steep forest engine",
            location_node_id="steep_forest",
            capabilities=frozenset({"fire_suppression", "pump", "water_delivery"}),
            capacity={"water_liters": 3500},
            readiness=0.88,
            vehicle_profile=default_fire_engine_profile(),
            metadata={"source": "synthetic"},
        ),
        Resource(
            resource_id="engine_bravo_paved_fast",
            resource_type="fire_engine",
            name="Paved access engine",
            location_node_id="base",
            capabilities=frozenset({"fire_suppression", "pump", "water_delivery", "structure_protection"}),
            capacity={"water_liters": 4200},
            readiness=0.92,
            vehicle_profile=default_fire_engine_profile(),
            metadata={"source": "synthetic"},
        ),
        Resource(
            resource_id="engine_charlie_safe_ridge",
            resource_type="fire_engine",
            name="Safe corridor engine",
            location_node_id="safe_valley",
            capabilities=frozenset({"fire_suppression", "pump", "water_delivery", "structure_protection"}),
            capacity={"water_liters": 4500},
            readiness=0.95,
            vehicle_profile=default_fire_engine_profile(),
            metadata={"source": "synthetic"},
        ),
        Resource(
            resource_id="engine_delta_fast_wrong_capability",
            resource_type="fire_engine",
            name="Transport-only engine",
            location_node_id="paved_mid",
            capabilities=frozenset({"transport"}),
            capacity={"water_liters": 1200},
            readiness=0.99,
            vehicle_profile=default_fire_engine_profile(),
            metadata={"source": "synthetic"},
        ),
        Resource(
            resource_id="engine_echo_trail_blocked",
            resource_type="fire_engine",
            name="Trail-side engine",
            location_node_id="narrow_cut",
            capabilities=frozenset({"fire_suppression", "pump", "water_delivery"}),
            capacity={"water_liters": 3000},
            readiness=0.90,
            vehicle_profile=default_fire_engine_profile(),
            metadata={"source": "synthetic"},
        ),
        Resource(
            resource_id="engine_foxtrot_unavailable",
            resource_type="fire_engine",
            name="Unavailable maintenance engine",
            location_node_id="base",
            status="maintenance",
            available=False,
            capabilities=frozenset({"fire_suppression", "pump", "water_delivery"}),
            capacity={"water_liters": 4000},
            readiness=0.0,
            vehicle_profile=default_fire_engine_profile(),
            metadata={"source": "synthetic"},
        ),
        Resource(
            resource_id="team_hotel_handcrew",
            resource_type="fire_team",
            name="Handcrew team",
            location_node_id="base",
            capabilities=frozenset({"fire_suppression", "handline", "structure_protection"}),
            capacity={"personnel": 18},
            readiness=0.86,
            vehicle_profile=light_utility_vehicle_profile(),
            metadata={"source": "synthetic"},
        ),
        Resource(
            resource_id="uav_recon_01",
            resource_type="uav",
            name="Recon UAV",
            longitude=101.0060,
            latitude=28.0060,
            capabilities=frozenset({"aerial_recon", "thermal_imaging"}),
            capacity={"battery_minutes": 45},
            readiness=0.93,
            mobility_mode="air",
            response_speed_kmh=80.0,
            metadata={"source": "synthetic", "route_risk_score": 0.05},
        ),
    ]


def fire_suppression_task(strategy: str = "balanced", engine_quantity: int = 1) -> ResourceTask:
    return ResourceTask(
        task_id="task_mountain_fire_suppression",
        task_type="fire_suppression",
        target_node_id="incident",
        priority="critical",
        minimum_resource_requirements=(
            ResourceRequirement("fire_engine", engine_quantity, frozenset({"fire_suppression", "pump"})),
        ),
        desired_resource_requirements=(
            ResourceRequirement("fire_team", 1, frozenset({"fire_suppression", "handline"})),
        ),
        strategy=strategy,  # type: ignore[arg-type]
        route_risk_weight=20.0,
        metadata={"source": "synthetic_mountain_resource_inventory", "synthetic": True},
    )


def multi_resource_fire_task(strategy: str = "balanced") -> ResourceTask:
    return ResourceTask(
        task_id="task_multi_resource_suppression",
        task_type="fire_suppression",
        target_node_id="incident",
        priority="critical",
        minimum_resource_requirements=(
            ResourceRequirement("fire_engine", 2, frozenset({"fire_suppression", "pump"})),
            ResourceRequirement("fire_team", 1, frozenset({"fire_suppression", "handline"})),
        ),
        strategy=strategy,  # type: ignore[arg-type]
        route_risk_weight=20.0,
        metadata={"source": "synthetic_mountain_resource_inventory", "synthetic": True},
    )


def reconnaissance_task(strategy: str = "fastest_response") -> ResourceTask:
    return ResourceTask(
        task_id="task_uav_recon",
        task_type="reconnaissance",
        target_node_id="incident",
        priority="high",
        minimum_resource_requirements=(ResourceRequirement("uav", 1, frozenset({"aerial_recon"})),),
        strategy=strategy,  # type: ignore[arg-type]
        metadata={"source": "synthetic_mountain_resource_inventory", "synthetic": True},
    )