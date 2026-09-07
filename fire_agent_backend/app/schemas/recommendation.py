from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


PackageStatus = Literal["draft", "recommended", "issued_to_command", "archived"]


class RecommendationRegenerateRequest(BaseModel):
    status: PackageStatus = "recommended"


class RecommendationPackageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    package_id: str
    event_id: str
    decision_run_id: str
    status: str
    summary: str
    route_package: dict[str, Any]
    uav_package: dict[str, Any]
    resource_package: dict[str, Any]
    command_package: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class RoutePlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    route_id: str
    package_id: str
    event_id: str
    name: str
    route_type: str
    risk: str
    summary: str
    geometry: dict[str, Any]
    metadata_json: dict[str, Any]
    created_at: datetime


class UavAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asset_id: str
    package_id: str
    event_id: str
    name: str
    status: str
    task: dict[str, Any]
    longitude: float
    latitude: float
    metadata_json: dict[str, Any]
    created_at: datetime


class ResourceInventoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    resource_id: str
    package_id: str
    event_id: str
    resource_type: str
    name: str
    quantity: int
    unit: str
    status: str
    target: str
    metadata_json: dict[str, Any]
    created_at: datetime


class RecommendationPayload(BaseModel):
    package: RecommendationPackageRead
    routes: list[RoutePlanRead]
    uavs: list[UavAssetRead]
    resources: list[ResourceInventoryRead]


class RecommendationEnvelope(BaseModel):
    ok: bool = True
    data: Any
