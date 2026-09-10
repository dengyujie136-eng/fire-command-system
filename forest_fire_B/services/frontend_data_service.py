# [Frontend-Data-API] 自动生成的前端友好接口
from __future__ import annotations

import json
import math
import time
from functools import wraps
from typing import Any, Callable, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.registry import PersonnelRegistry, ResourceRegistry, UAVRegistry
from services.scene_cache import get_scene_cache_value


def cache(ttl: int = 30):
    def decorator(func: Callable):
        storage: dict = {}

        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = (func.__name__, args[1:] if args else args, tuple(sorted(kwargs.items())))
            now = time.time()
            if key in storage:
                value, expires_at = storage[key]
                if now < expires_at:
                    return value
            value = await func(*args, **kwargs)
            storage[key] = (value, now + ttl)
            return value

        return wrapper

    return decorator


class FrontendDataService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _parse_location(self, location: Optional[str]) -> dict[str, Any]:
        if not location:
            return {"lng": 0.0, "lat": 0.0, "alt": 0.0}
        try:
            parsed = json.loads(location)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        return {"raw": location}

    @cache(ttl=30)
    async def list_uavs(self, scene_id: str | None = None) -> list[dict[str, Any]]:
        stmt = select(UAVRegistry)
        if scene_id:
            stmt = stmt.where((UAVRegistry.scene_id == scene_id) | (UAVRegistry.scene_id.is_(None)))
        result = await self.db.execute(stmt.order_by(UAVRegistry.last_update.desc()))
        rows = result.scalars().all()
        items = []
        for row in rows:
            items.append({
                "id": row.id,
                "name": row.name,
                "type": row.type,
                "status": row.status,
                "location": self._parse_location(row.location),
                "scene_id": row.scene_id,
                "last_update": row.last_update.isoformat() if row.last_update else None,
            })
        return items

    @cache(ttl=30)
    async def list_resources(self, type: str | None = None, scene_id: str | None = None) -> dict[str, Any]:
        stmt = select(ResourceRegistry)
        if type:
            stmt = stmt.where(ResourceRegistry.type == type)
        if scene_id:
            stmt = stmt.where((ResourceRegistry.scene_id == scene_id) | (ResourceRegistry.scene_id.is_(None)))
        result = await self.db.execute(stmt.order_by(ResourceRegistry.last_update.desc()))
        rows = result.scalars().all()
        items = []
        stats: dict[str, int] = {}
        for row in rows:
            stats[row.type] = stats.get(row.type, 0) + 1
            items.append({
                "id": row.id,
                "name": row.name,
                "type": row.type,
                "status": row.status,
                "location": self._parse_location(row.location),
                "scene_id": row.scene_id,
                "last_update": row.last_update.isoformat() if row.last_update else None,
            })
        return {"items": items, "stats": stats}

    @cache(ttl=30)
    async def list_personnel(self, role: str | None = None, scene_id: str | None = None) -> list[dict[str, Any]]:
        stmt = select(PersonnelRegistry)
        if role:
            stmt = stmt.where(PersonnelRegistry.type == role)
        if scene_id:
            stmt = stmt.where((PersonnelRegistry.scene_id == scene_id) | (PersonnelRegistry.scene_id.is_(None)))
        result = await self.db.execute(stmt.order_by(PersonnelRegistry.last_update.desc()))
        rows = result.scalars().all()
        return [
            {
                "id": row.id,
                "name": row.name,
                "type": row.type,
                "status": row.status,
                "location": self._parse_location(row.location),
                "scene_id": row.scene_id,
                "last_update": row.last_update.isoformat() if row.last_update else None,
            }
            for row in rows
        ]

    @cache(ttl=30)
    async def get_fire_geojson(self, scene_id: str | None) -> dict[str, Any]:
        cached = get_scene_cache_value(scene_id or "") if scene_id else None
        if cached and cached.get("current_fire_geojson"):
            fire_line = cached["current_fire_geojson"]
            return {
                "type": "FeatureCollection",
                "features": [fire_line] if fire_line.get("type") == "Feature" else fire_line.get("features", []),
                "scene_id": scene_id,
                "coords": fire_line.get("geometry", {}).get("coordinates", []),
            }

        features = []
        if scene_id:
            base_lng = 114.3 + (sum(ord(c) for c in scene_id) % 20) * 0.001
            base_lat = 30.5 + (sum(ord(c) for c in scene_id) % 20) * 0.001
        else:
            base_lng, base_lat = 114.3, 30.5

        for idx in range(3):
            ring = [
                [base_lng + idx * 0.01, base_lat],
                [base_lng + idx * 0.01 + 0.005, base_lat + 0.001],
                [base_lng + idx * 0.01 + 0.010, base_lat],
            ]
            features.append({
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": ring},
                "properties": {
                    "id": f"fire-line-{idx + 1}",
                    "scene_id": scene_id,
                    "step": idx + 1,
                },
            })
        return {"type": "FeatureCollection", "features": features, "scene_id": scene_id, "coords": features[-1]["geometry"]["coordinates"] if features else []}

    @cache(ttl=30)
    async def get_fire_stat(self, scene_id: str | None) -> dict[str, Any]:
        cached = get_scene_cache_value(scene_id or "") if scene_id else None
        if cached:
            return {
                "scene_id": scene_id,
                "current_step": cached.get("current_step", 0),
                "metrics": {
                    "fire_area": cached.get("fire_area", 0.0),
                    "fire_area_km2": cached.get("fire_area", 0.0),
                    "spread_speed": cached.get("spread_speed", 0.0),
                    "uav_online": 3,
                    "resource_ready": 5,
                    "personnel_ready": 8,
                },
                "risk_level": cached.get("risk_level", "medium"),
                "agent_summary": cached.get("agent_summary", ""),
                "wind_params": cached.get("wind_params", {}),
                "stats": cached.get("stats", {}),
            }
        base = sum(ord(c) for c in scene_id) if scene_id else 100
        area = round(2.5 + (base % 8) * 1.3, 2)
        risk_score = min(100, 35 + (base % 9) * 7)
        risk_level = "critical" if risk_score >= 80 else "high" if risk_score >= 60 else "medium" if risk_score >= 40 else "low"
        return {
            "scene_id": scene_id,
            "metrics": {
                "fire_area_km2": area,
                "active_hotspots": 3 + base % 5,
                "uav_online": 2 + base % 3,
                "resource_ready": 5 + base % 7,
                "personnel_ready": 10 + base % 15,
            },
            "risk_level": risk_level,
            "risk_score": risk_score,
            "agent_summary": "",
        }
