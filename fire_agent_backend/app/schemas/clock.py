from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.observation import FusionResultRead, ObservationRead, TrustedFirePointRead


class SimulationClockRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    scenario_id: str
    status: str
    current_minute: int
    duration_minutes: int
    tick_interval_seconds: float
    time_segments: list[dict[str, Any]]
    started_at: datetime | None
    updated_at: datetime


class EnvironmentSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    snapshot_id: str
    event_id: str
    scenario_id: str
    time_minute: int
    temperature_c: float
    humidity_percent: float
    wind_speed_m_s: float
    wind_direction_deg: float
    fuel_moisture: float
    fire_weather_index: float
    payload: dict[str, Any]
    created_at: datetime


class ClockStartRequest(BaseModel):
    scenario_id: str | None = None
    tick_interval_seconds: float | None = Field(default=None, gt=0, le=60)
    reset: bool = False


class ClockStepRequest(BaseModel):
    minutes: int | None = Field(default=None, gt=0, le=120)


class ClockStatePayload(BaseModel):
    clock: SimulationClockRead
    environment: EnvironmentSnapshotRead | None = None
    observations: list[ObservationRead] = []
    fusion_result: FusionResultRead | None = None
    trusted_fire_point: TrustedFirePointRead | None = None


class ClockEnvelope(BaseModel):
    ok: bool = True
    data: Any
