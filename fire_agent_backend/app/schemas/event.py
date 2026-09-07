from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


EventStatus = Literal[
    "created",
    "observing",
    "confirmed",
    "simulating",
    "deciding",
    "dispatching",
    "replanning",
    "completed",
    "failed",
    "closed",
]


class IgnitionPoint(BaseModel):
    longitude: float = 101.269444
    latitude: float = 28.530278
    confidence: float = Field(default=0.87, ge=0, le=1)


class StartSimulatedEventRequest(BaseModel):
    scenario_id: str = "muli_lier_village"
    name: str | None = None
    ignition_point: IgnitionPoint | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FireEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    name: str
    status: str
    scenario_id: str
    source_mode: str
    ignition_longitude: float
    ignition_latitude: float
    ignition_confidence: float
    started_at: datetime
    closed_at: datetime | None
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class EventTimelineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timeline_id: str
    event_id: str
    event_type: str
    status: str
    title: str
    message: str
    payload: dict[str, Any]
    created_at: datetime


class FireEventDetail(BaseModel):
    event: FireEventRead
    timeline: list[EventTimelineRead]


class EventEnvelope(BaseModel):
    ok: bool = True
    data: FireEventRead | FireEventDetail | list[EventTimelineRead] | None = None
