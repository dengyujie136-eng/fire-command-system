# [UI-Component-Ready] 自动生成的前端友好接口
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from routers.websocket import manager
from services.frontend_data_service import FrontendDataService

router = APIRouter(prefix="/api", tags=["frontend-data"])


class APIResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: Any = None
    meta: dict[str, Any] = Field(default_factory=dict)


def ok(data: Any = None, message: str = "ok", **meta: Any) -> dict[str, Any]:
    return APIResponse(code=0, message=message, data=data, meta=meta).model_dump()


@router.get("/fire/list", response_model=APIResponse)
async def get_fire_list(scene_id: Optional[str] = Query(default=None), format: str = Query(default="ui"), db: AsyncSession = Depends(get_db)):
    service = FrontendDataService(db)
    raw = await service.get_fire_geojson(scene_id)
    if format == "raw":
        return ok(data=raw, scene_id=scene_id, format=format)
    features = []
    for idx, feature in enumerate(raw.get("features", []), start=1):
        props = feature.get("properties", {})
        # [UI-Component-Ready] 前端对接示例
        # A同学可直接使用：
        # const res = await fetch('/api/fire/list?scene_id=demo')
        # const { chart_data, summary_cards } = res.data
        # echarts.setOption({ xAxis: chart_data.xAxis, series: chart_data.series })
        props["popup"] = {
            "scene_id": scene_id,
            "type": feature.get("geometry", {}).get("type", "LineString"),
            "step": props.get("step", idx),
            "risk_hint": "火势向东蔓延",
        }
        feature["properties"] = props
        features.append(feature)
    return ok(data={"type": "FeatureCollection", "features": features, "coords": raw.get("coords", [])}, scene_id=scene_id, format=format)


@router.get("/fire/stat", response_model=APIResponse)
async def get_fire_stat(scene_id: Optional[str] = Query(default=None), format: str = Query(default="ui"), db: AsyncSession = Depends(get_db)):
    service = FrontendDataService(db)
    raw = await service.get_fire_stat(scene_id)
    if format == "raw":
        return ok(data=raw, scene_id=scene_id, format=format)
    ui_data = {
        "_raw": raw,
        "risk_level": "high" if raw.get("risk_level") in {"high", "critical"} else raw.get("risk_level", "medium"),
        "chart_data": {
            "xAxis": ["T0", "T1", "T2"],
            "series": [{"name": "面积(km²)", "data": [0.1, 0.45, 0.85]}],
        },
        "summary_cards": [
            {"label": "过火面积", "value": "0.85km²", "color": "#ff4d4f", "trend": "+12%"},
            {"label": "风速", "value": "6.5m/s", "color": "#1677ff", "trend": "稳定"},
            {"label": "当前步数", "value": "2", "color": "#52c41a", "trend": "+1"},
        ],
        "metrics": raw.get("metrics", {}),
        "agent_summary": raw.get("agent_summary", ""),
        "wind_params": raw.get("wind_params", {}),
        "stats": raw.get("stats", {}),
    }
    return ok(data=ui_data, scene_id=scene_id, format=format)


@router.get("/uav/list", response_model=APIResponse)
async def get_uav_list(scene_id: Optional[str] = Query(default=None), db: AsyncSession = Depends(get_db)):
    service = FrontendDataService(db)
    items = await service.list_uavs(scene_id)
    merged = []
    for item in items:
        cache_item = manager.get_uav_cache(f"mock-{item['id']}") or manager.get_uav_cache(item.get("name", ""))
        if cache_item:
            item = {**item, "location": {"lng": cache_item.get("lng"), "lat": cache_item.get("lat"), "alt": cache_item.get("alt")}, "ws_cache": cache_item}
        merged.append(item)
    if not merged:
        merged = [{"id": 1, "name": "UAV-001", "type": "recon", "status": "online", "location": {"lng": 114.3, "lat": 30.5, "alt": 100}, "scene_id": scene_id, "last_update": None, "ws_cache": manager.get_uav_cache("mock-uav-001") }]
    return ok(data=merged, scene_id=scene_id, cached=bool(manager.get_uav_cache("mock-uav-001")))


@router.get("/resource/list", response_model=APIResponse)
async def get_resource_list(type: Optional[str] = Query(default=None), scene_id: Optional[str] = Query(default=None), db: AsyncSession = Depends(get_db)):
    service = FrontendDataService(db)
    raw = await service.list_resources(type=type, scene_id=scene_id)
    if type:
        raw["quick_actions"] = [{"label": "一键派发消防车", "endpoint": "/decision/resource-dispatch", "params": {"type": "fire_truck"}}]
    rows = raw.get("items", [])
    columns = [
        {"title": "名称", "dataIndex": "name", "key": "name"},
        {"title": "类型", "dataIndex": "type", "key": "type"},
        {"title": "状态", "dataIndex": "status", "key": "status"},
        {"title": "位置", "dataIndex": "location", "key": "location"},
    ]
    raw["table_data"] = {"columns": columns, "rows": rows}
    raw["quick_actions"] = raw.get("quick_actions", [{"label": "一键派发消防车", "endpoint": "/decision/resource-dispatch", "params": {"type": "fire_truck"}}])
    return ok(data={"_raw": raw, **raw}, scene_id=scene_id, type=type)


@router.get("/personnel/list", response_model=APIResponse)
async def get_personnel_list(role: Optional[str] = Query(default=None), scene_id: Optional[str] = Query(default=None), db: AsyncSession = Depends(get_db)):
    service = FrontendDataService(db)
    data = await service.list_personnel(role=role, scene_id=scene_id)
    return ok(data=data, scene_id=scene_id, role=role)
