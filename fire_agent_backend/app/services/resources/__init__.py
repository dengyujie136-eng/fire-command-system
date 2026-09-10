"""Standalone wildfire resource dispatch calculation unit."""

from app.services.resources.allocation import calculate_resource_dispatch
from app.services.resources.models import Resource, ResourceDispatchResult, ResourceRequirement, ResourceTask
from app.services.resources.sample_resources import (
    build_mountain_resource_inventory,
    fire_suppression_task,
    multi_resource_fire_task,
    reconnaissance_task,
)

__all__ = [
    "Resource",
    "ResourceDispatchResult",
    "ResourceRequirement",
    "ResourceTask",
    "build_mountain_resource_inventory",
    "calculate_resource_dispatch",
    "fire_suppression_task",
    "multi_resource_fire_task",
    "reconnaissance_task",
]