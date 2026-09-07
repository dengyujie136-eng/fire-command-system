# [Frontend-Data-API] 自动生成的前端友好接口
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, JSON, String, Text, Index

from database import Base


class UAVRegistry(Base):
    __tablename__ = "uav_registry"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(128), nullable=False, index=True)
    type = Column(String(64), nullable=False, index=True, default="recon")
    status = Column(String(32), nullable=False, index=True, default="idle")
    location = Column(Text, nullable=True)
    scene_id = Column(String(64), nullable=True, index=True)
    last_update = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_uav_registry_scene_status", "scene_id", "status"),
    )


class ResourceRegistry(Base):
    __tablename__ = "resource_registry"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(128), nullable=False, index=True)
    type = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, index=True, default="available")
    location = Column(Text, nullable=True)
    scene_id = Column(String(64), nullable=True, index=True)
    last_update = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_resource_registry_scene_type", "scene_id", "type"),
    )


class PersonnelRegistry(Base):
    __tablename__ = "personnel_registry"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(128), nullable=False, index=True)
    type = Column(String(64), nullable=False, index=True, default="rescuer")
    status = Column(String(32), nullable=False, index=True, default="available")
    location = Column(Text, nullable=True)
    scene_id = Column(String(64), nullable=True, index=True)
    last_update = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_personnel_registry_scene_type", "scene_id", "type"),
    )


class DispatchMaterialInventory(Base):
    __tablename__ = "dispatch_material_inventory"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    item_type = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=False, index=True)
    unit = Column(String(32), nullable=False, default="unit")
    total_quantity = Column(Float, nullable=False, default=0.0)
    available_quantity = Column(Float, nullable=False, default=0.0)
    reorder_threshold = Column(Float, nullable=False, default=0.0)
    replacement_cycle_hours = Column(Integer, nullable=True)
    location = Column(Text, nullable=True)
    scene_id = Column(String(64), nullable=True, index=True)
    last_update = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_dispatch_material_scene_type", "scene_id", "item_type"),
    )


class DispatchPersonnelInventory(Base):
    __tablename__ = "dispatch_personnel_inventory"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    station_name = Column(String(128), nullable=False, index=True)
    role = Column(String(64), nullable=False, index=True)
    total_count = Column(Integer, nullable=False, default=0)
    available_count = Column(Integer, nullable=False, default=0)
    location = Column(Text, nullable=True)
    scene_id = Column(String(64), nullable=True, index=True)
    last_update = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_dispatch_personnel_scene_role", "scene_id", "role"),
    )


class DispatchUAVInventory(Base):
    __tablename__ = "dispatch_uav_inventory"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    uav_id = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    capability = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="available", index=True)
    battery_percent = Column(Integer, nullable=False, default=100)
    location = Column(Text, nullable=True)
    scene_id = Column(String(64), nullable=True, index=True)
    last_update = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_dispatch_uav_scene_capability", "scene_id", "capability"),
    )


class DispatchActionLog(Base):
    __tablename__ = "dispatch_action_log"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    scene_id = Column(String(64), nullable=True, index=True)
    task_id = Column(String(128), nullable=True, index=True)
    action_type = Column(String(64), nullable=False, index=True)
    summary = Column(Text, nullable=False)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
