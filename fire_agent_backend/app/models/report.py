from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DecisionReport(Base):
    __tablename__ = "decision_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    event_id: Mapped[str] = mapped_column(String(80), ForeignKey("fire_events.event_id", ondelete="CASCADE"), index=True)
    decision_run_id: Mapped[str] = mapped_column(String(100), default="", index=True)
    recommendation_package_id: Mapped[str] = mapped_column(String(100), default="", index=True)
    recalculation_id: Mapped[str] = mapped_column(String(100), default="", index=True)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(40), default="generated", index=True)
    format: Mapped[str] = mapped_column(String(40), default="markdown")
    summary: Mapped[str] = mapped_column(String(800), default="")
    sections: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    content_markdown: Mapped[str] = mapped_column(Text, default="")
    generated_by: Mapped[str] = mapped_column(String(100), default="fire_agent_backend")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
