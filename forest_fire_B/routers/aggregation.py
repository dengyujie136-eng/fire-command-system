# [Aggregation-Facade] 指挥中心与地图聚合接口 v1.0
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from routers.websocket import manager
from services.frontend_data_service import FrontendDataService
from services.scene_cache import get_scene_cache_value

router = APIRouter(tags=["Aggregation"])


class APIResponse(BaseModel):
    code: int = 200
    message: str = "ok"
    data: Any = None
    meta: dict[str, Any] = Field(default_factory=dict)
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "code": 200,
                    "message": "ok",
                    "data": {
                        "fires": {"count": 1, "risk_level": "high"},
                        "uavs": {"online": 1, "total": 3},
                        "resources": {"available": 2, "in_use": 1},
                        "personnel": {"total": 3, "active": 2},
                        "alerts": 1,
                        "timestamp": "2026-04-29T12:00:00+00:00",
                    },
                    "meta": {"scene_id": "seed-demo-001"},
                }
            ]
        }
    )


class FireOverview(BaseModel):
    count: int = 0
    risk_level: Literal["high", "medium", "low"] = "low"


class OverviewData(BaseModel):
    fires: FireOverview = Field(default_factory=FireOverview)
    uavs: dict[str, int] = Field(default_factory=lambda: {"online": 0, "total": 0})
    resources: dict[str, int] = Field(default_factory=lambda: {"available": 0, "in_use": 0})
    personnel: dict[str, int] = Field(default_factory=lambda: {"total": 0, "active": 0})
    alerts: int = 0
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class FusionData(BaseModel):
    confidence: float = 0.0
    sources: list[str] = Field(default_factory=list)
    fire_estimation: dict[str, Any] = Field(default_factory=dict)
    recommendation: str = ""
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MapLayerResponse(BaseModel):
    layers: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CommandOverviewResponse(BaseModel):
    fires: FireOverview = Field(default_factory=FireOverview)
    uavs: dict[str, int] = Field(default_factory=lambda: {"online": 0, "total": 0})
    resources: dict[str, int] = Field(default_factory=lambda: {"available": 0, "in_use": 0})
    personnel: dict[str, int] = Field(default_factory=lambda: {"total": 0, "active": 0})
    alerts: int = 0
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def ok(data: Any, **meta: Any) -> dict[str, Any]:
    return APIResponse(code=200, message="ok", data=data, meta=meta).model_dump()


def _parse_location(location: Any) -> tuple[float, float, float]:
    if isinstance(location, dict):
        return float(location.get("lng", 0.0)), float(location.get("lat", 0.0)), float(location.get("alt", 0.0))
    return 0.0, 0.0, 0.0


@router.get(
    "/command/overview",
    response_model=APIResponse,
    response_model_exclude_none=True,
    summary="指挥中心总览",
    responses={
        200: {
            "description": "成功响应示例",
            "content": {
                "application/json": {
                    "example": {
                        "code": 200,
                        "message": "ok",
                        "data": {
                            "fires": {"count": 1, "risk_level": "high"},
                            "uavs": {"online": 1, "total": 3},
                            "resources": {"available": 2, "in_use": 1},
                            "personnel": {"total": 3, "active": 2},
                            "alerts": 1,
                            "timestamp": "2026-04-29T12:00:00+00:00",
                        },
                        "meta": {"scene_id": "seed-demo-001"},
                    }
                }
            },
        }
    },
)
async def command_overview(scene_id: str | None = Query(default=None, description="场景ID"), db: AsyncSession = Depends(get_db)):
    service = FrontendDataService(db)

    async def _fire():
        return get_scene_cache_value(scene_id or "") or {}

    async def _uavs():
        return await service.list_uavs(scene_id)

    async def _resources():
        return await service.list_resources(scene_id=scene_id)

    async def _personnel():
        return await service.list_personnel(scene_id=scene_id)

    async def _alerts():
        cache_data = manager.get_uav_cache(f"heartbeat-{scene_id or 'global'}") or {}
        return 1 if cache_data else 0

    fire_cache, uavs, resources, personnel, alerts = await asyncio.gather(_fire(), _uavs(), _resources(), _personnel(), _alerts())

    # [UI-Dashboard-Ready] 指挥中心聚合，前端可直接渲染卡片
    count = 1 if fire_cache else 0
    risk_level = fire_cache.get("risk_level", "low") if isinstance(fire_cache, dict) else "low"
    if risk_level not in {"high", "medium", "low"}:
        risk_level = "low"

    online = 0
    for item in uavs:
        status = str(item.get("status", "")).lower()
        if status in {"online", "flying", "active", "idle"}:
            online += 1
    total_uavs = len(uavs)

    available = 0
    in_use = 0
    for item in resources.get("items", []):
        status = str(item.get("status", "")).lower()
        if status in {"available", "idle"}:
            available += 1
        else:
            in_use += 1

    active = 0
    for item in personnel:
        status = str(item.get("status", "")).lower()
        if status in {"on_duty", "on_mission", "active", "available"}:
            active += 1

    data = CommandOverviewResponse(
        fires=FireOverview(count=count, risk_level=risk_level),
        uavs={"online": online, "total": total_uavs},
        resources={"available": available, "in_use": in_use},
        personnel={"total": len(personnel), "active": active},
        alerts=int(alerts),
    )
    return ok(data.model_dump(), scene_id=scene_id)


@router.get(
    "/map/all",
    response_model=APIResponse,
    response_model_exclude_none=True,
    summary="多图层地图聚合",
    responses={
        200: {
            "description": "成功响应示例",
            "content": {
                "application/json": {
                    "example": {
                        "code": 200,
                        "message": "ok",
                        "data": {
                            "layers": {
                                "fire": {
                                    "type": "FeatureCollection",
                                    "features": [
                                        {
                                            "type": "Feature",
                                            "geometry": {"type": "LineString", "coordinates": [[114.3, 30.5], [114.31, 30.5], [114.32, 30.5]]},
                                            "properties": {
                                                "scene_id": "seed-demo-001",
                                                "type": "fire_line",
                                                "step": 3,
                                                "popup": {"scene_id": "seed-demo-001", "type": "fire_line", "step": 3, "risk_hint": "火势向东蔓延"},
                                            },
                                        }
                                    ],
                                },
                                "uav": [{"id": 1, "lng": 114.31, "lat": 30.51, "status": "idle", "battery": 0}],
                            },
                            "timestamp": "2026-04-29T12:00:00+00:00",
                        },
                        "meta": {"scene_id": "seed-demo-001", "layers": "fire,uav"},
                    }
                }
            },
        }
    },
)
async def map_all(layers: str = Query(..., description="逗号分隔图层: fire,uav,resource,personnel"), scene_id: str | None = Query(default=None), db: AsyncSession = Depends(get_db)):
    allowed = {"fire", "uav", "resource", "personnel"}
    requested = [x.strip() for x in layers.split(",") if x.strip()]
    if not requested or any(layer not in allowed for layer in requested):
        raise HTTPException(status_code=400, detail="layers 仅允许 fire,uav,resource,personnel 组合")

    service = FrontendDataService(db)
    result: dict[str, Any] = {}

    async def fire_task():
        return await service.get_fire_geojson(scene_id)

    async def uav_task():
        items = await service.list_uavs(scene_id)
        return [
            {
                "id": item.get("id"),
                "lng": _parse_location(item.get("location"))[0],
                "lat": _parse_location(item.get("location"))[1],
                "status": item.get("status", "unknown"),
                "battery": item.get("battery", 0),
            }
            for item in items
        ]

    async def resource_task():
        payload = await service.list_resources(scene_id=scene_id)
        rows = payload.get("items", [])
        parsed = []
        for item in rows:
            lng, lat, _ = _parse_location(item.get("location"))
            parsed.append({"id": item.get("id"), "type": item.get("type"), "lng": lng, "lat": lat, "quantity": item.get("quantity", 1)})
        return parsed

    async def personnel_task():
        items = await service.list_personnel(scene_id=scene_id)
        parsed = []
        for item in items:
            lng, lat, _ = _parse_location(item.get("location"))
            parsed.append({"id": item.get("id"), "name": item.get("name"), "role": item.get("type"), "lng": lng, "lat": lat, "status": item.get("status", "unknown")})
        return parsed

    tasks = {
        "fire": fire_task(),
        "uav": uav_task(),
        "resource": resource_task(),
        "personnel": personnel_task(),
    }
    gathered = await asyncio.gather(*[tasks[layer] for layer in requested])
    for layer, payload in zip(requested, gathered):
        result[layer] = payload

    data = MapLayerResponse(layers=result)
    return ok(data.model_dump(), scene_id=scene_id, layers=layers)


@router.get(
    "/fusion/result",
    response_model=APIResponse,
    response_model_exclude_none=True,
    summary="多源融合结果",
    responses={
        200: {
            "description": "成功响应示例",
            "content": {
                "application/json": {
                    "example": {
                        "code": 200,
                        "message": "ok",
                        "data": {
                            "confidence": 0.87,
                            "sources": ["satellite_stub", "uav_telemetry", "open_meteo"],
                            "fire_estimation": {"area_km2": 0.85, "trend": "expanding"},
                            "recommendation": "建议增派无人机加密侦察东侧区域",
                            "updated_at": "2026-04-29T12:00:00+00:00",
                        },
                        "meta": {"scene_id": "seed-demo-001"},
                    }
                }
            },
        }
    },
)
async def fusion_result(scene_id: str | None = Query(default=None), db: AsyncSession = Depends(get_db)):
    service = FrontendDataService(db)
    scene = get_scene_cache_value(scene_id or "") if scene_id else None

    async def _uavs():
        return await service.list_uavs(scene_id)

    async def _ingest():
        return scene.get("ingest_status") if isinstance(scene, dict) else None

    uavs, ingest_status = await asyncio.gather(_uavs(), _ingest())
    fire_area = float(scene.get("fire_area", 0.0)) if isinstance(scene, dict) else 0.0
    wind_speed = float((scene.get("wind_params") or {}).get("wind_speed", 0.0)) if isinstance(scene, dict) else 0.0
    online = sum(1 for item in uavs if str(item.get("status", "")).lower() in {"online", "flying", "active", "idle"})

    confidence = 0.6 + (0.1 * min(online / 3, 1)) + (0.1 * min(wind_speed / 10, 1))
    confidence = max(0.0, min(1.0, round(confidence, 2)))

    prev_fire_area = float(scene.get("previous_fire_area", fire_area)) if isinstance(scene, dict) else fire_area
    if fire_area > prev_fire_area:
        trend = "expanding"
    elif fire_area < prev_fire_area:
        trend = "declining"
    else:
        trend = "stabilizing"

    sources = list(ingest_status) if isinstance(ingest_status, list) and ingest_status else ["satellite_stub", "uav_telemetry", "open_meteo"]
    recommendation = "建议增派无人机加密侦察东侧区域" if trend == "expanding" else "建议保持当前布控并持续监测"

    # [UI-Dashboard-Ready] 融合页可直接用于仪表盘和建议卡
    data = FusionData(
        confidence=confidence,
        sources=sources,
        fire_estimation={"area_km2": fire_area, "trend": trend},
        recommendation=recommendation,
    )
    return ok(data.model_dump(), scene_id=scene_id)


# 前端对接速查
# // 指挥中心卡片
# const overview = await get('/api/command/overview?scene_id=demo')
# // 地图多图层
# const layers = await get('/api/map/all?layers=fire,uav&scene_id=demo')
# // 融合页面
# const fusion = await get('/api/fusion/result?scene_id=demo')
