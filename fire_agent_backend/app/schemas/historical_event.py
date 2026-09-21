from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HistoricalEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    name: str
    country: str
    region: str
    bbox: dict[str, Any]
    centroid_longitude: float
    centroid_latitude: float
    started_at: datetime
    ended_at: datetime
    burned_area_km2: float | None
    duration_days: float | None
    max_impact_area_km2: float | None
    losses: dict[str, Any]
    data_availability: dict[str, Any]
    environmental_data: dict[str, Any]
    model_data: dict[str, Any]
    source_mode: str
    source_url: str
    source_citation: str
    notes: str


class HistoricalEventQuery(BaseModel):
    text: str = Field(default="", max_length=500)
    country: str = "United States"
    region: str = "California"
    last_years: int = Field(default=5, ge=1, le=50)
    sort_by: str = "burned_area_km2"
    limit: int = Field(default=5, ge=1, le=20)


class HistoricalEventSearchEnvelope(BaseModel):
    ok: bool = True
    data: dict[str, Any]
