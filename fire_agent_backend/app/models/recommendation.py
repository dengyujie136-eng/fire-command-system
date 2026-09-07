from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RecommendationPackage(Base):
    __tablename__ = "recommendation_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    package_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    event_id: Mapped[str] = mapped_column(String(80), ForeignKey("fire_events.event_id", ondelete="CASCADE"), index=True)
    decision_run_id: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(40), default="recommended", index=True)
    summary: Mapped[str] = mapped_column(String(500), default="")
    route_package: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    uav_package: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    resource_package: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    command_package: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RoutePlan(Base):
    __tablename__ = "route_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    route_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    package_id: Mapped[str] = mapped_column(String(100), ForeignKey("recommendation_packages.package_id", ondelete="CASCADE"), index=True)
    event_id: Mapped[str] = mapped_column(String(80), ForeignKey("fire_events.event_id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    route_type: Mapped[str] = mapped_column(String(60), index=True)
    risk: Mapped[str] = mapped_column(String(40), default="moderate")
    summary: Mapped[str] = mapped_column(String(500), default="")
    geometry: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class UavAsset(Base):
    __tablename__ = "uav_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    package_id: Mapped[str] = mapped_column(String(100), ForeignKey("recommendation_packages.package_id", ondelete="CASCADE"), index=True)
    event_id: Mapped[str] = mapped_column(String(80), ForeignKey("fire_events.event_id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(40), default="recommended", index=True)
    task: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    longitude: Mapped[float] = mapped_column(Float, default=0)
    latitude: Mapped[float] = mapped_column(Float, default=0)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class ResourceInventory(Base):
    __tablename__ = "resource_inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    package_id: Mapped[str] = mapped_column(String(100), ForeignKey("recommendation_packages.package_id", ondelete="CASCADE"), index=True)
    event_id: Mapped[str] = mapped_column(String(80), ForeignKey("fire_events.event_id", ondelete="CASCADE"), index=True)
    resource_type: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(160))
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    unit: Mapped[str] = mapped_column(String(40), default="")
    status: Mapped[str] = mapped_column(String(40), default="recommended", index=True)
    target: Mapped[str] = mapped_column(String(200), default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
