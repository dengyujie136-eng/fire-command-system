from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DecisionRun(Base):
    __tablename__ = "decision_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    decision_run_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    event_id: Mapped[str] = mapped_column(String(80), ForeignKey("fire_events.event_id", ondelete="CASCADE"), index=True)
    scenario_id: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(40), default="completed", index=True)
    provider: Mapped[str] = mapped_column(String(60), default="zhipu")
    model: Mapped[str] = mapped_column(String(120), default="glm-4.6")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    recommended_plan: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    input_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    raw_llm_output: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class AgentPacket(Base):
    __tablename__ = "agent_packets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    packet_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    decision_run_id: Mapped[str] = mapped_column(String(100), ForeignKey("decision_runs.decision_run_id", ondelete="CASCADE"), index=True)
    event_id: Mapped[str] = mapped_column(String(80), ForeignKey("fire_events.event_id", ondelete="CASCADE"), index=True)
    packet_type: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
