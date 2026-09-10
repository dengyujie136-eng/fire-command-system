from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ScenarioDefinition(Base):
    __tablename__ = "scenario_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    location_name: Mapped[str] = mapped_column(String(300))
    longitude: Mapped[float] = mapped_column(Float)
    latitude: Mapped[float] = mapped_column(Float)
    coordinate_precision: Mapped[str] = mapped_column(String(40), default="exact")
    duration_minutes: Mapped[int] = mapped_column(Integer, default=120)
    default_tick_interval_seconds: Mapped[float] = mapped_column(Float, default=2.0)
    time_segments: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    profiles: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SimulationClock(Base):
    __tablename__ = "simulation_clocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    scenario_id: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(40), default="idle", index=True)
    current_minute: Mapped[int] = mapped_column(Integer, default=0)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=120)
    tick_interval_seconds: Mapped[float] = mapped_column(Float, default=2.0)
    time_segments: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EnvironmentSnapshot(Base):
    __tablename__ = "environment_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    event_id: Mapped[str] = mapped_column(String(80), index=True)
    scenario_id: Mapped[str] = mapped_column(String(100), index=True)
    time_minute: Mapped[int] = mapped_column(Integer, index=True)
    temperature_c: Mapped[float] = mapped_column(Float)
    humidity_percent: Mapped[float] = mapped_column(Float)
    wind_speed_m_s: Mapped[float] = mapped_column(Float)
    wind_direction_deg: Mapped[float] = mapped_column(Float)
    fuel_moisture: Mapped[float] = mapped_column(Float)
    fire_weather_index: Mapped[float] = mapped_column(Float)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
