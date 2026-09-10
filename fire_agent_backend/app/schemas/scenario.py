from typing import Any

from pydantic import BaseModel, ConfigDict


class ScenarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scenario_id: str
    name: str
    location_name: str
    longitude: float
    latitude: float
    coordinate_precision: str
    duration_minutes: int
    default_tick_interval_seconds: float
    time_segments: list[dict[str, Any]]
    profiles: dict[str, Any]
    enabled: bool


class ScenarioEnvelope(BaseModel):
    ok: bool = True
    data: Any
