from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HistoricalFireEvent(Base):
    __tablename__ = "historical_fire_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    country: Mapped[str] = mapped_column(String(80), index=True)
    region: Mapped[str] = mapped_column(String(120), index=True)
    bbox: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    centroid_longitude: Mapped[float] = mapped_column(Float)
    centroid_latitude: Mapped[float] = mapped_column(Float)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    burned_area_km2: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_days: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_impact_area_km2: Mapped[float | None] = mapped_column(Float, nullable=True)
    losses: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    data_availability: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    environmental_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    model_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_mode: Mapped[str] = mapped_column(String(60), default="historical_record")
    source_url: Mapped[str] = mapped_column(Text, default="")
    source_citation: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
