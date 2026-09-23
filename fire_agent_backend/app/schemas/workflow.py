from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


WorkflowStatus = Literal[
    "PENDING", "READY", "RUNNING", "WAITING_FOR_INPUT", "COMPLETED", "FAILED", "UNAVAILABLE", "SKIPPED"
]


class WorkflowCreateRequest(BaseModel):
    mode: Literal["historical", "realtime", "exercise"] = "historical"
    horizon_minutes: int = Field(default=360, ge=60, le=1440)
    threat_buffer_km: float = Field(default=0.45, ge=0, le=5)
    candidate_id: str | None = None
    confirmation_id: str | None = None


class WorkflowSpreadRerunRequest(BaseModel):
    """Explicit Command Center what-if inputs for a confirmed workflow fire point."""

    horizon_minutes: int = Field(default=360, ge=60, le=1440)
    wind_speed_m_s: float = Field(ge=0, le=60)
    wind_direction_deg: float = Field(ge=0, lt=360)
    temperature_c: float = Field(ge=-30, le=65)
    humidity_percent: float = Field(ge=0, le=100)
    precipitation_mm_h: float = Field(default=0, ge=0, le=200)
    fuel_moisture: float = Field(ge=0.01, le=0.8)
    fire_weather_index: float = Field(ge=0, le=100)


class HumanVerificationRequest(BaseModel):
    action: Literal["confirm", "reject", "uncertain"]
    confirmation_id: str | None = None
    note: str = Field(default="", max_length=1000)


class ScenarioGenerateRequest(BaseModel):
    mode: Literal["RECOMMENDED", "MANUAL", "EXERCISE"] = "RECOMMENDED"
    command_post: tuple[float, float] | None = None
    staging_area: tuple[float, float] | None = None
    resource_points: list[tuple[float, float]] = Field(default_factory=list, max_length=20)


class ScenarioConfirmRequest(BaseModel):
    command_location_id: str | None = None
    staging_location_id: str | None = None
    note: str = Field(default="", max_length=1000)
    run_downstream: bool = True


class CommanderReviewRequest(BaseModel):
    action: Literal["approve", "revise", "regenerate"]
    note: str = Field(default="", max_length=1000)


class WorkflowStageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stage: str
    status: WorkflowStatus
    progress: int
    message: str
    result_id: str | None
    error: str | None
    metadata_json: dict[str, Any]
    started_at: datetime | None
    finished_at: datetime | None


class WorkflowRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workflow_run_id: str
    event_id: str
    mode: str
    status: WorkflowStatus
    current_stage: str
    candidate_id: str | None
    visual_case_id: str | None
    confirmation_id: str | None
    spread_run_id: str | None
    spatial_analysis_id: str | None
    scenario_id: str | None
    resource_plan_id: str | None
    route_plan_id: str | None
    decision_run_id: str | None
    recommendation_id: str | None
    human_confirmation_state: str
    horizon_minutes: int
    threat_buffer_km: float
    metadata_json: dict[str, Any]
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    stages: list[WorkflowStageRead] = Field(default_factory=list)
    scenario: dict[str, Any] | None = None
    artifacts: dict[str, Any] = Field(default_factory=dict)


class WorkflowEnvelope(BaseModel):
    ok: bool = True
    data: Any
