from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.recommendation import RecommendationPayload


DisturbanceType = Literal[
    "wind_shift",
    "road_unavailable",
    "uav_availability_reduced",
    "protected_target_priority_changed",
    "weather_risk_increased",
]


class ScenarioDisturbanceCreate(BaseModel):
    disturbance_type: DisturbanceType
    assumption: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    created_by: str = "command"


class RecalculationRequest(BaseModel):
    disturbance_id: str | None = None
    disturbance: ScenarioDisturbanceCreate | None = None
    status: Literal["draft", "recommended", "issued_to_command"] = "recommended"


class ScenarioDisturbanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    disturbance_id: str
    event_id: str
    disturbance_type: str
    status: str
    assumption: str
    parameters: dict[str, Any]
    created_by: str
    created_at: datetime


class RecalculationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recalculation_id: str
    event_id: str
    disturbance_id: str
    status: str
    base_package_id: str
    new_package_id: str
    change_summary: dict[str, Any]
    before_snapshot: dict[str, Any]
    after_snapshot: dict[str, Any]
    created_at: datetime


class RecalculationPayload(BaseModel):
    disturbance: ScenarioDisturbanceRead
    recalculation: RecalculationRunRead
    recommendation: RecommendationPayload


class DisturbanceEnvelope(BaseModel):
    ok: bool = True
    data: Any


class RecalculationEnvelope(BaseModel):
    ok: bool = True
    data: Any
