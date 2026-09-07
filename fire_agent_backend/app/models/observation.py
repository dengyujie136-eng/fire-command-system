from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Observation(Base):
    __tablename__ = "observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    observation_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    event_id: Mapped[str] = mapped_column(String(80), ForeignKey("fire_events.event_id", ondelete="CASCADE"), index=True)
    source_type: Mapped[str] = mapped_column(String(60), index=True)
    source_name: Mapped[str] = mapped_column(String(120), index=True)
    stage: Mapped[str] = mapped_column(String(80), index=True, default="observation")
    longitude: Mapped[float] = mapped_column(Float)
    latitude: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    data_source_mode: Mapped[str] = mapped_column(String(40), default="simulation", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvidenceChain(Base):
    __tablename__ = "evidence_chains"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evidence_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    event_id: Mapped[str] = mapped_column(String(80), ForeignKey("fire_events.event_id", ondelete="CASCADE"), index=True)
    observation_id: Mapped[str] = mapped_column(String(100), index=True)
    source_type: Mapped[str] = mapped_column(String(60), index=True)
    reliability: Mapped[float] = mapped_column(Float, default=0.0)
    weight: Mapped[float] = mapped_column(Float, default=0.0)
    contribution: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class FusionResult(Base):
    __tablename__ = "fusion_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fusion_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    event_id: Mapped[str] = mapped_column(String(80), ForeignKey("fire_events.event_id", ondelete="CASCADE"), index=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    longitude: Mapped[float] = mapped_column(Float)
    latitude: Mapped[float] = mapped_column(Float)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    evidence_sources: Mapped[list[str]] = mapped_column(JSON, default=list)
    decision: Mapped[str] = mapped_column(String(80), default="pending")
    quality: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    data_source_mode: Mapped[str] = mapped_column(String(40), default="simulation", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class TrustedFirePoint(Base):
    __tablename__ = "trusted_fire_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trusted_point_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    event_id: Mapped[str] = mapped_column(String(80), ForeignKey("fire_events.event_id", ondelete="CASCADE"), index=True)
    fusion_id: Mapped[str] = mapped_column(String(100), index=True)
    longitude: Mapped[float] = mapped_column(Float)
    latitude: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    level: Mapped[str] = mapped_column(String(40), default="medium", index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    data_source_mode: Mapped[str] = mapped_column(String(40), default="simulation", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
