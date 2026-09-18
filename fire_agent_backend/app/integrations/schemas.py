from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.spatial_analysis import SpatialAnalysisPayload
from app.schemas.spread import SpreadEnvironmentFrame, SpreadRunPayload


class TrustedIgnition(BaseModel):
    event_id: str
    confirmation_id: str
    visual_case_id: str
    source_candidate_id: str
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    observed_at: datetime
    confirmed_at: datetime
    confidence: float = Field(ge=0, le=1)
    source: Literal["visual_fire_confirmation"] = "visual_fire_confirmation"
    evidence_ids: list[str] = Field(default_factory=list)
    confirmation_method: str
    is_simulated: bool


class EventContext(BaseModel):
    event_id: str
    name: str
    status: str
    scenario_id: str
    source_mode: str
    started_at: datetime | None = None


class CandidateContext(BaseModel):
    candidate_id: str
    visual_case_id: str
    observed_at: datetime
    longitude: float
    latitude: float
    upstream_status: str
    visual_status: str
    imagery_status: str
    cluster_point_count: int | None = None
    cluster_mean_confidence: float | None = None
    cluster_max_frp_mw: float | None = None


class CapabilityStatus(BaseModel):
    status: Literal["ready", "completed", "unavailable", "failed"]
    reason: str | None = None
    mode: Literal["real", "demo", "synthetic"] = "real"
    source: str | None = None


class IncidentContext(BaseModel):
    event: EventContext
    candidate: CandidateContext
    ignition: TrustedIgnition
    visual_findings: list[dict[str, Any]] = Field(default_factory=list)
    weather: list[SpreadEnvironmentFrame] = Field(default_factory=list)
    spread: SpreadRunPayload
    spatial: SpatialAnalysisPayload
    resource: CapabilityStatus
    route: CapabilityStatus


class CommandWorkflowRequest(BaseModel):
    confirmation_id: str | None = None
    candidate_id: str | None = None
    horizon_minutes: int = Field(default=180, ge=30, le=1440)
    threat_buffer_km: float = Field(default=0.45, ge=0, le=5)
    force_provider: str | None = None


class WorkflowIdentifiers(BaseModel):
    candidate_id: str
    visual_case_id: str
    confirmation_id: str
    spread_run_id: str
    spatial_analysis_id: str
    decision_run_id: str
    recommendation_id: str


class CommandWorkflowResult(BaseModel):
    workflow_status: Literal["completed", "failed"]
    identifiers: WorkflowIdentifiers
    confirmed_point: TrustedIgnition
    situation: dict[str, Any]
    spread: dict[str, Any]
    spatial_risk: dict[str, Any]
    resource: CapabilityStatus
    route: CapabilityStatus
    command_plan: dict[str, Any]
    recommendation: dict[str, Any]
    agent_results: list[dict[str, Any]]
    warnings: list[str] = Field(default_factory=list)


class CommandWorkflowEnvelope(BaseModel):
    ok: bool = True
    data: Any
