from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SpatialAnalysisRequest(BaseModel):
    threat_buffer_km: float = Field(default=0.45, ge=0, le=5)
    blocked_road_ids: list[str] = Field(default_factory=list)
    include_routes: bool = True
    input_source: str = "upstream_mock"


class SpatialAnalysisRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    analysis_id: str
    event_id: str
    spread_run_id: str
    status: str
    analysis_engine: str
    input_source: str
    summary: dict[str, Any]
    parameters: dict[str, Any]
    impact_geojson: dict[str, Any]
    route_geojson: dict[str, Any]
    warnings: list[str]
    is_simulated: bool
    created_at: datetime


class SpatialImpactRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    record_id: str
    analysis_id: str
    event_id: str
    object_id: str
    object_type: str
    name: str
    severity: str
    affected: bool
    distance_to_fire_km: float
    population: int
    geometry: dict[str, Any]
    attributes: dict[str, Any]
    created_at: datetime


class EmergencyRoutePlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    route_id: str
    analysis_id: str
    event_id: str
    route_type: str
    name: str
    status: str
    risk_level: str
    distance_km: float
    eta_minutes: float
    geometry: dict[str, Any]
    attributes: dict[str, Any]
    created_at: datetime


class SpatialAnalysisPayload(BaseModel):
    run: SpatialAnalysisRunRead
    impacts: list[SpatialImpactRecordRead]
    routes: list[EmergencyRoutePlanRead]


class SpatialAnalysisEnvelope(BaseModel):
    ok: bool = True
    data: Any
