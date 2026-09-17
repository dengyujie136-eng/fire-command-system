from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Float, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RealtimeObservation(Base):
    __tablename__ = "realtime_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    observation_id: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    region_id: Mapped[str] = mapped_column(String(80), index=True)
    source: Mapped[str] = mapped_column(String(120), index=True)
    product: Mapped[str] = mapped_column(String(120), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_file: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RealtimeHotspot(Base):
    __tablename__ = "realtime_hotspots"
    __table_args__ = (
        UniqueConstraint("region_id", "source_record_id", name="uq_realtime_hotspot_source"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_realtime_hotspot_longitude"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_realtime_hotspot_latitude"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    detection_id: Mapped[str] = mapped_column(String(220), unique=True, index=True)
    region_id: Mapped[str] = mapped_column(String(80), index=True)
    observation_id: Mapped[str] = mapped_column(String(180), index=True)
    source_record_id: Mapped[str] = mapped_column(String(180), index=True)
    source: Mapped[str] = mapped_column(String(120), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    longitude: Mapped[float] = mapped_column(Float)
    latitude: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="candidate", index=True)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
