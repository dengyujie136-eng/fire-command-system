from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FireEvent(Base):
    __tablename__ = "fire_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True, default="created")
    scenario_id: Mapped[str] = mapped_column(String(100), index=True, default="muli_lier_village")
    source_mode: Mapped[str] = mapped_column(String(40), default="simulation")
    ignition_longitude: Mapped[float] = mapped_column(Float)
    ignition_latitude: Mapped[float] = mapped_column(Float)
    ignition_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    timeline: Mapped[list["EventTimeline"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="EventTimeline.created_at",
    )


class EventTimeline(Base):
    __tablename__ = "event_timeline"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timeline_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    event_id: Mapped[str] = mapped_column(String(80), ForeignKey("fire_events.event_id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    event: Mapped[FireEvent] = relationship(back_populates="timeline")
