from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    event_id: Mapped[str] = mapped_column(String(80), ForeignKey("fire_events.event_id", ondelete="CASCADE"), index=True)
    scenario_id: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(40), default="completed", index=True)
    engine: Mapped[str] = mapped_column(String(60), default="fallback")
    forefire_attempted: Mapped[bool] = mapped_column(Boolean, default=False)
    forefire_available: Mapped[bool] = mapped_column(Boolean, default=False)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=True)
    start_minute: Mapped[int] = mapped_column(Integer, default=0)
    horizon_minutes: Mapped[int] = mapped_column(Integer, default=120)
    step_minutes: Mapped[int] = mapped_column(Integer, default=30)
    ignition_longitude: Mapped[float] = mapped_column(Float)
    ignition_latitude: Mapped[float] = mapped_column(Float)
    final_area_km2: Mapped[float] = mapped_column(Float, default=0)
    max_radius_km: Mapped[float] = mapped_column(Float, default=0)
    spread_direction_deg: Mapped[float] = mapped_column(Float, default=0)
    risk_level: Mapped[str] = mapped_column(String(40), default="medium")
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class FireFrontStep(Base):
    __tablename__ = "fire_front_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    step_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    run_id: Mapped[str] = mapped_column(String(100), ForeignKey("simulation_runs.run_id", ondelete="CASCADE"), index=True)
    event_id: Mapped[str] = mapped_column(String(80), ForeignKey("fire_events.event_id", ondelete="CASCADE"), index=True)
    time_minute: Mapped[int] = mapped_column(Integer, index=True)
    elapsed_seconds: Mapped[int] = mapped_column(Integer, index=True)
    area_km2: Mapped[float] = mapped_column(Float, default=0)
    radius_km: Mapped[float] = mapped_column(Float, default=0)
    spread_direction_deg: Mapped[float] = mapped_column(Float, default=0)
    fireline_geojson: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
