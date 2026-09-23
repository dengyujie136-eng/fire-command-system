from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ImageryAcquisitionTask(Base):
    """Persisted data-agent search and download state."""

    __tablename__ = "imagery_acquisition_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("fire_events.event_id"), index=True)
    phase: Mapped[str] = mapped_column(String(24))
    time_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    time_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), index=True)
    message: Mapped[str] = mapped_column(Text, default="")
    scene_id: Mapped[str | None] = mapped_column(String(240))
    download_url: Mapped[str | None] = mapped_column(String(1000))
    source_name: Mapped[str | None] = mapped_column(String(160))
    required_bands: Mapped[list[str]] = mapped_column(JSON, default=list)
    available_bands: Mapped[list[str]] = mapped_column(JSON, default=list)
    local_files: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
