from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SpreadRunRequest(BaseModel):
    horizon_minutes: int = Field(default=120, ge=30, le=720)
    step_minutes: int = Field(default=30, ge=5, le=120)
    prefer_forefire: bool = True


class SimulationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    event_id: str
    scenario_id: str
    status: str
    engine: str
    forefire_attempted: bool
    forefire_available: bool
    fallback_used: bool
    start_minute: int
    horizon_minutes: int
    step_minutes: int
    ignition_longitude: float
    ignition_latitude: float
    final_area_km2: float
    max_radius_km: float
    spread_direction_deg: float
    risk_level: str
    input_snapshot: dict[str, Any]
    result_summary: dict[str, Any]
    error_message: str
    created_at: datetime


class FireFrontStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step_id: str
    run_id: str
    event_id: str
    time_minute: int
    elapsed_seconds: int
    area_km2: float
    radius_km: float
    spread_direction_deg: float
    fireline_geojson: dict[str, Any]
    created_at: datetime


class SpreadRunPayload(BaseModel):
    run: SimulationRunRead
    steps: list[FireFrontStepRead]
    geojson: dict[str, Any]


class SpreadEnvelope(BaseModel):
    ok: bool = True
    data: Any
