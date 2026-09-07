from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ScenarioDisturbance(Base):
    __tablename__ = "scenario_disturbances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    disturbance_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    event_id: Mapped[str] = mapped_column(String(80), ForeignKey("fire_events.event_id", ondelete="CASCADE"), index=True)
    disturbance_type: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(40), default="active", index=True)
    assumption: Mapped[str] = mapped_column(String(500), default="")
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(100), default="command")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class RecalculationRun(Base):
    __tablename__ = "recalculation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recalculation_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    event_id: Mapped[str] = mapped_column(String(80), ForeignKey("fire_events.event_id", ondelete="CASCADE"), index=True)
    disturbance_id: Mapped[str] = mapped_column(String(100), ForeignKey("scenario_disturbances.disturbance_id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="completed", index=True)
    base_package_id: Mapped[str] = mapped_column(String(100), default="", index=True)
    new_package_id: Mapped[str] = mapped_column(String(100), default="", index=True)
    change_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    before_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    after_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
