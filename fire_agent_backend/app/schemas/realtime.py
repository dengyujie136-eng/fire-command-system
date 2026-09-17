from datetime import datetime

from pydantic import BaseModel, Field


class RealtimeSyncRequest(BaseModel):
    region_id: str = Field(min_length=1, max_length=80)


class RealtimeRegion(BaseModel):
    id: str
    label: str
    satellite: str
    platform: str
    coverage: str
    bbox: list[float]
    refresh_minutes: int
    supported: bool
    source_mode: str


class RealtimeHotspotRead(BaseModel):
    detection_id: str
    region_id: str
    source: str
    observed_at: datetime
    detected_at: datetime
    longitude: float
    latitude: float
    confidence: float
    status: str
    source_asset_id: str
    algorithm: str
    attributes: dict


class RealtimeSyncResponse(BaseModel):
    ready: bool
    region_id: str
    source: str
    observed_at: datetime | None = None
    fetched_at: datetime
    detection_status: str
    hotspots: list[RealtimeHotspotRead] = Field(default_factory=list)
    total: int = 0
    error: str | None = None
