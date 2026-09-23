from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_run_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    event_id: Mapped[str] = mapped_column(String(80), ForeignKey("fire_events.event_id", ondelete="CASCADE"), index=True)
    mode: Mapped[str] = mapped_column(String(32), default="historical", index=True)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
    current_stage: Mapped[str] = mapped_column(String(64), default="data_preparation", index=True)
    candidate_id: Mapped[str | None] = mapped_column(String(240), nullable=True)
    visual_case_id: Mapped[str | None] = mapped_column(String(180), nullable=True)
    confirmation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    spread_run_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    spatial_analysis_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    scenario_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resource_plan_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    route_plan_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    decision_run_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    recommendation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    human_confirmation_state: Mapped[str] = mapped_column(String(40), default="AI_SUGGESTED")
    horizon_minutes: Mapped[int] = mapped_column(Integer, default=360)
    threat_buffer_km: Mapped[float] = mapped_column(Float, default=0.45)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkflowStageRun(Base):
    __tablename__ = "workflow_stage_runs"
    __table_args__ = (UniqueConstraint("workflow_run_id", "stage", name="uq_workflow_stage"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_run_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("workflow_runs.workflow_run_id", ondelete="CASCADE"), index=True
    )
    stage: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(String(500), default="")
    result_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EmergencyScenario(Base):
    __tablename__ = "emergency_scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    workflow_run_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("workflow_runs.workflow_run_id", ondelete="CASCADE"), index=True
    )
    event_id: Mapped[str] = mapped_column(String(80), ForeignKey("fire_events.event_id", ondelete="CASCADE"), index=True)
    mode: Mapped[str] = mapped_column(String(32), default="RECOMMENDED", index=True)
    source: Mapped[str] = mapped_column(String(32), default="recommended")
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    rule_version: Mapped[str] = mapped_column(String(40), default="scenario-rules-v0.2")
    size_class: Mapped[str] = mapped_column(String(20), default="MEDIUM")
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ScenarioLocation(Base):
    __tablename__ = "scenario_locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    scenario_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("emergency_scenarios.scenario_id", ondelete="CASCADE"), index=True
    )
    location_type: Mapped[str] = mapped_column(String(40), index=True)
    rank: Mapped[int] = mapped_column(Integer, default=1)
    longitude: Mapped[float] = mapped_column(Float)
    latitude: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(32), default="recommended")
    selected: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    score: Mapped[float] = mapped_column(Float, default=0)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    reason: Mapped[list[str]] = mapped_column(JSON, default=list)
    missing_data: Mapped[list[str]] = mapped_column(JSON, default=list)
    limitations: Mapped[list[str]] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ScenarioResource(Base):
    __tablename__ = "scenario_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    scenario_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("emergency_scenarios.scenario_id", ondelete="CASCADE"), index=True
    )
    resource_type: Mapped[str] = mapped_column(String(60), index=True)
    name: Mapped[str] = mapped_column(String(160))
    longitude: Mapped[float] = mapped_column(Float)
    latitude: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), default="available")
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list)
    capacity: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    readiness: Mapped[float] = mapped_column(Float, default=1.0)
    mobility_mode: Mapped[str] = mapped_column(String(20), default="ground")
    mode: Mapped[str] = mapped_column(String(20), default="SCENARIO", index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ScenarioResourcePlan(Base):
    __tablename__ = "scenario_resource_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_plan_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    scenario_id: Mapped[str] = mapped_column(String(100), ForeignKey("emergency_scenarios.scenario_id"), index=True)
    workflow_run_id: Mapped[str] = mapped_column(String(100), ForeignKey("workflow_runs.workflow_run_id"), index=True)
    mode: Mapped[str] = mapped_column(String(20), default="SCENARIO")
    status: Mapped[str] = mapped_column(String(32), default="completed")
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScenarioRoutePlan(Base):
    __tablename__ = "scenario_route_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    route_plan_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    scenario_id: Mapped[str] = mapped_column(String(100), ForeignKey("emergency_scenarios.scenario_id"), index=True)
    workflow_run_id: Mapped[str] = mapped_column(String(100), ForeignKey("workflow_runs.workflow_run_id"), index=True)
    mode: Mapped[str] = mapped_column(String(20), default="SCENARIO_ROUTE")
    status: Mapped[str] = mapped_column(String(32), default="completed")
    geometry: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
