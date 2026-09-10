from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


CASE_STATUSES = ("received", "imagery_searching", "imagery_ready", "analyzing", "confirmed", "rejected", "uncertain", "failed")
RUN_STATUSES = ("queued", "running", "succeeded", "timeout", "invalid_output", "provider_error", "cancelled")
TERMINAL_STATUSES = ("confirmed", "rejected", "uncertain", "failed")
UPSTREAM_STATUSES = ("candidate", "under_review", "confirmed", "rejected", "expired")
UPSTREAM_IMAGERY_STATUSES = ("pending", "available", "unavailable")


def _allowed_values(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


class VisualVerificationCaseRecord(Base):
    __tablename__ = "visual_verification_cases"
    __table_args__ = (
        UniqueConstraint("event_id", "source_candidate_id", "version", name="uq_visual_case_source_version"),
        CheckConstraint(_allowed_values("status", CASE_STATUSES), name="ck_visual_case_status"),
        CheckConstraint(_allowed_values("upstream_status", UPSTREAM_STATUSES), name="ck_visual_case_upstream_status"),
        CheckConstraint(_allowed_values("imagery_status", UPSTREAM_IMAGERY_STATUSES), name="ck_visual_case_imagery_status"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_visual_case_longitude"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_visual_case_latitude"),
        CheckConstraint("version >= 1", name="ck_visual_case_version"),
        Index("ix_visual_case_event_status", "event_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visual_case_id: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    source_candidate_id: Mapped[str] = mapped_column(String(240), nullable=False)
    upstream_schema_version: Mapped[str] = mapped_column(String(80), nullable=False)
    upstream_status: Mapped[str] = mapped_column(String(32), nullable=False)
    event_id: Mapped[str] = mapped_column(String(160), nullable=False)
    event_name: Mapped[str] = mapped_column(String(240), nullable=False)
    observation_id: Mapped[str | None] = mapped_column(String(120))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    imagery_status: Mapped[str] = mapped_column(String(32), nullable=False)
    data_owner: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    replay_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    product_fields: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    upstream_payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="received")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class VisualCaseAssetRecord(Base):
    __tablename__ = "visual_case_assets"
    __table_args__ = (
        UniqueConstraint("visual_case_id", "source_asset_id", "asset_role", name="uq_visual_case_asset_role"),
        Index("ix_visual_asset_case", "visual_case_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visual_case_id: Mapped[str] = mapped_column(ForeignKey("visual_verification_cases.visual_case_id", ondelete="CASCADE"), nullable=False)
    source_asset_id: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_role: Mapped[str] = mapped_column(String(32), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_name: Mapped[str | None] = mapped_column(String(160))
    mime_type: Mapped[str | None] = mapped_column(String(120))
    acquired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_uri: Mapped[str] = mapped_column(String(1000), nullable=False)
    preview_uri: Mapped[str | None] = mapped_column(String(1000))
    quality_status: Mapped[str] = mapped_column(String(32), nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class VisualImageDerivativeRecord(Base):
    __tablename__ = "visual_image_derivatives"
    __table_args__ = (Index("ix_visual_derivative_case", "visual_case_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    derivative_id: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    visual_case_id: Mapped[str] = mapped_column(ForeignKey("visual_verification_cases.visual_case_id", ondelete="CASCADE"), nullable=False)
    source_asset_id: Mapped[str] = mapped_column(String(120), nullable=False)
    derivative_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_uri: Mapped[str] = mapped_column(String(1000), nullable=False)
    preview_uri: Mapped[str | None] = mapped_column(String(1000))
    crs: Mapped[str | None] = mapped_column(String(64))
    extent_geojson: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    processing_parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class VisualAnalysisRunRecord(Base):
    __tablename__ = "visual_analysis_runs"
    __table_args__ = (
        CheckConstraint(_allowed_values("run_status", RUN_STATUSES), name="ck_visual_run_status"),
        CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_visual_run_duration"),
        Index("ix_visual_run_case_status", "visual_case_id", "run_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_run_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    visual_case_id: Mapped[str] = mapped_column(ForeignKey("visual_verification_cases.visual_case_id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    model_version: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    run_status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    is_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class VisualFindingRecord(Base):
    __tablename__ = "visual_findings"
    __table_args__ = (
        CheckConstraint("confidence IS NULL OR confidence BETWEEN 0 AND 1", name="ck_visual_finding_confidence"),
        Index("ix_visual_finding_run_type", "analysis_run_id", "finding_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    finding_id: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    analysis_run_id: Mapped[str] = mapped_column(ForeignKey("visual_analysis_runs.analysis_run_id", ondelete="CASCADE"), nullable=False)
    finding_type: Mapped[str] = mapped_column(String(64), nullable=False)
    detected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    geometry_geojson: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    evidence_source: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FireConfirmationRecord(Base):
    __tablename__ = "fire_confirmations"
    __table_args__ = (
        UniqueConstraint("visual_case_id", "version", name="uq_fire_confirmation_version"),
        CheckConstraint(_allowed_values("status", TERMINAL_STATUSES), name="ck_fire_confirmation_status"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_fire_confirmation_confidence"),
        CheckConstraint("longitude IS NULL OR longitude BETWEEN -180 AND 180", name="ck_fire_confirmation_longitude"),
        CheckConstraint("latitude IS NULL OR latitude BETWEEN -90 AND 90", name="ck_fire_confirmation_latitude"),
        CheckConstraint("version >= 1", name="ck_fire_confirmation_version"),
        CheckConstraint("status != 'confirmed' OR (confirmed_at IS NOT NULL AND longitude IS NOT NULL AND latitude IS NOT NULL)", name="ck_confirmed_fire_requires_location"),
        Index("ix_fire_confirmation_case_current", "visual_case_id", "is_current"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    confirmation_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    visual_case_id: Mapped[str] = mapped_column(ForeignKey("visual_verification_cases.visual_case_id", ondelete="CASCADE"), nullable=False)
    source_candidate_id: Mapped[str] = mapped_column(String(240), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    longitude: Mapped[float | None] = mapped_column(Float)
    latitude: Mapped[float | None] = mapped_column(Float)
    area_geojson: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    confirmation_method: Mapped[str] = mapped_column(String(80), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(80), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
