from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ObservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    observation_id: str
    event_id: str
    source_type: str
    source_name: str
    stage: str
    longitude: float
    latitude: float
    confidence: float
    observed_at: datetime
    attributes: dict[str, Any]
    is_simulated: bool
    data_source_mode: str
    created_at: datetime


class EvidenceChainRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    evidence_id: str
    event_id: str
    observation_id: str
    source_type: str
    reliability: float
    weight: float
    contribution: float
    explanation: str
    created_at: datetime


class FusionResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fusion_id: str
    event_id: str
    confirmed: bool
    confidence: float
    longitude: float
    latitude: float
    evidence_count: int
    evidence_sources: list[str]
    decision: str
    quality: dict[str, Any]
    is_simulated: bool
    data_source_mode: str
    created_at: datetime


class TrustedFirePointRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trusted_point_id: str
    event_id: str
    fusion_id: str
    longitude: float
    latitude: float
    confidence: float
    level: str
    description: str
    is_simulated: bool
    data_source_mode: str
    created_at: datetime


class ObservationSimulationResult(BaseModel):
    observations: list[ObservationRead]
    evidence_chain: list[EvidenceChainRead]
    fusion_result: FusionResultRead
    trusted_fire_point: TrustedFirePointRead


class ObservationEnvelope(BaseModel):
    ok: bool = True
    data: Any
