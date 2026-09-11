from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SpatialAnalysisRun(Base):
    __tablename__ = "spatial_analysis_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    event_id: Mapped[str] = mapped_column(String(80), ForeignKey("fire_events.event_id", ondelete="CASCADE"), index=True)
    spread_run_id: Mapped[str] = mapped_column(String(100), ForeignKey("simulation_runs.run_id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="completed", index=True)
    analysis_engine: Mapped[str] = mapped_column(String(80), default="python_geometry_astar")
    input_source: Mapped[str] = mapped_column(String(60), default="upstream_mock", index=True)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    impact_geojson: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    route_geojson: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class SpatialImpactRecord(Base):
    __tablename__ = "spatial_impact_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    analysis_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("spatial_analysis_runs.analysis_id", ondelete="CASCADE"),
        index=True,
    )
    event_id: Mapped[str] = mapped_column(String(80), ForeignKey("fire_events.event_id", ondelete="CASCADE"), index=True)
    object_id: Mapped[str] = mapped_column(String(100), index=True)
    object_type: Mapped[str] = mapped_column(String(60), index=True)
    name: Mapped[str] = mapped_column(String(180))
    severity: Mapped[str] = mapped_column(String(40), default="low", index=True)
    affected: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    distance_to_fire_km: Mapped[float] = mapped_column(Float, default=0)
    population: Mapped[int] = mapped_column(Integer, default=0)
    geometry: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class EmergencyRoutePlan(Base):
    __tablename__ = "emergency_route_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    route_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    analysis_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("spatial_analysis_runs.analysis_id", ondelete="CASCADE"),
        index=True,
    )
    event_id: Mapped[str] = mapped_column(String(80), ForeignKey("fire_events.event_id", ondelete="CASCADE"), index=True)
    route_type: Mapped[str] = mapped_column(String(60), index=True)
    name: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(40), default="available", index=True)
    risk_level: Mapped[str] = mapped_column(String(40), default="medium", index=True)
    distance_km: Mapped[float] = mapped_column(Float, default=0)
    eta_minutes: Mapped[float] = mapped_column(Float, default=0)
    geometry: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
