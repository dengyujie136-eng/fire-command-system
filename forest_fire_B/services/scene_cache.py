# [Scene-Cache-Integration] 场景缓存层
from __future__ import annotations

import time
from typing import Any, Dict, Optional


class SceneCache:
    """轻量级场景缓存，支持 TTL。"""

    def __init__(self, ttl: int = 300):
        self.ttl = ttl
        self._store: Dict[str, Dict[str, Any]] = {}

    def _is_expired(self, record: Dict[str, Any]) -> bool:
        return time.time() >= record.get("expires_at", 0)

    def set(self, scene_id: str, data: dict[str, Any], ttl: Optional[int] = None) -> None:
        expires_in = ttl if ttl is not None else self.ttl
        expires_at = float("inf") if expires_in == 0 else time.time() + expires_in
        self._store[scene_id] = {"value": data, "expires_at": expires_at}

    def get(self, scene_id: str) -> Optional[dict[str, Any]]:
        record = self._store.get(scene_id)
        if not record:
            return None
        if self._is_expired(record):
            self._store.pop(scene_id, None)
            return None
        return record["value"]

    def delete(self, scene_id: str) -> None:
        self._store.pop(scene_id, None)

    def build_scene_payload(
        self,
        scene_id: str,
        fire_line: dict[str, Any],
        current_step: int,
        fire_area: float,
        spread_speed: float,
        wind_params: dict[str, Any],
        risk_level: str,
        agent_summary: str,
    ) -> dict[str, Any]:
        return {
            "scene_id": scene_id,
            "current_step": current_step,
            "fire_area": fire_area,
            "spread_speed": spread_speed,
            "wind_params": wind_params,
            "risk_level": risk_level,
            "agent_summary": agent_summary,
            "current_fire_geojson": fire_line,
            "stats": {
                "fire_area": fire_area,
                "spread_speed": spread_speed,
                "current_step": current_step,
            },
        }


scene_cache = SceneCache(ttl=300)


def get_scene_cache() -> SceneCache:
    return scene_cache


def set_scene_cache(scene_id: str, data: dict[str, Any], ttl: Optional[int] = None) -> None:
    scene_cache.set(scene_id, data, ttl)


def get_scene_cache_value(scene_id: str) -> Optional[dict[str, Any]]:
    return scene_cache.get(scene_id)
