from __future__ import annotations

import asyncio
import json
import math
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.llm.providers import get_llm_provider
from app.models.event import FireEvent
from app.models.realtime import RealtimeHotspot, RealtimeObservation
from app.models.workflow import WorkflowRun
from app.services.realtime_service import REGIONS, sync_region
from app.services.workflow_runtime_service import data_readiness


GEOCODE_CACHE_TTL_SECONDS = 3600
_GEOCODE_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_GEOCODE_LOCK = asyncio.Lock()
_GEOCODE_LAST_REQUEST_AT = 0.0


ASSISTANT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "geocode_location",
            "description": "把用户提供的真实地名转换为经纬度和边界。不得猜测坐标。",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "完整地点名称，例如四川省雅安市"},
                    "country_hint": {"type": "string", "description": "可选国家或地区提示"},
                },
                "required": ["location"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "select_realtime_region",
            "description": "根据真实经纬度选择系统可用的 FIRMS 实时区域。",
            "parameters": {
                "type": "object",
                "properties": {
                    "longitude": {"type": "number"},
                    "latitude": {"type": "number"},
                },
                "required": ["longitude", "latitude"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sync_realtime_hotspots",
            "description": "从 NASA FIRMS 同步指定区域的近实时卫星热异常候选点。",
            "parameters": {
                "type": "object",
                "properties": {"region_id": {"type": "string"}},
                "required": ["region_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_hotspots_in_aoi",
            "description": "按中心点和半径筛选最近一次 FIRMS 观测中的真实候选火点。",
            "parameters": {
                "type": "object",
                "properties": {
                    "region_id": {"type": "string"},
                    "longitude": {"type": "number"},
                    "latitude": {"type": "number"},
                    "radius_km": {"type": "number", "minimum": 5, "maximum": 500},
                },
                "required": ["region_id", "longitude", "latitude"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_events_near_location",
            "description": "查询系统中是否已有靠近指定坐标的真实或历史事件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "longitude": {"type": "number"},
                    "latitude": {"type": "number"},
                    "radius_km": {"type": "number", "minimum": 1, "maximum": 300},
                },
                "required": ["longitude", "latitude"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_data_readiness",
            "description": "检查一个已存在事件的 FIRMS、气象、DEM、燃料和影像是否齐全。",
            "parameters": {
                "type": "object",
                "properties": {"event_id": {"type": "string"}},
                "required": ["event_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_workflow_status",
            "description": "读取一个已存在事件最新工作流的真实状态。",
            "parameters": {
                "type": "object",
                "properties": {"event_id": {"type": "string"}},
                "required": ["event_id"],
                "additionalProperties": False,
            },
        },
    },
]


def _distance_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    radius = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    value = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(max(0.0, 1 - value)))


def select_region_for_point(longitude: float, latitude: float) -> dict[str, Any]:
    matches = []
    for region_id, config in REGIONS.items():
        west, south, east, north = config["bbox"]
        if west <= longitude <= east and south <= latitude <= north:
            area = abs((east - west) * (north - south))
            matches.append((not config["supported"], area, region_id, config))
    if not matches:
        return {
            "ok": False,
            "reason": "当前系统没有覆盖该坐标的实时监测区域",
            "longitude": longitude,
            "latitude": latitude,
        }
    _, _, region_id, config = sorted(matches, key=lambda item: (item[0], item[1]))[0]
    return {
        "ok": True,
        "region_id": region_id,
        "label": config["label"],
        "supported": bool(config["supported"]),
        "coverage": config["coverage"],
        "source": config["satellite"],
        "bbox": config["bbox"],
    }


async def geocode_location(location: str, country_hint: str = "") -> dict[str, Any]:
    global _GEOCODE_LAST_REQUEST_AT

    query = " ".join(part for part in (location.strip(), country_hint.strip()) if part).strip()
    if not query or len(query) > 160:
        return {"ok": False, "reason": "地点为空或过长"}
    cache_key = query.casefold()
    cached = _GEOCODE_CACHE.get(cache_key)
    if cached and time.monotonic() - cached[0] < GEOCODE_CACHE_TTL_SECONDS:
        return {**cached[1], "cache_hit": True}

    settings = get_settings()
    endpoint = f"{settings.geocoder_base_url.rstrip('/')}/search"
    async with _GEOCODE_LOCK:
        cached = _GEOCODE_CACHE.get(cache_key)
        if cached and time.monotonic() - cached[0] < GEOCODE_CACHE_TTL_SECONDS:
            return {**cached[1], "cache_hit": True}
        wait_seconds = max(0.0, 1.0 - (time.monotonic() - _GEOCODE_LAST_REQUEST_AT))
        if wait_seconds:
            await asyncio.sleep(wait_seconds)
        async with httpx.AsyncClient(timeout=settings.geocoder_timeout_seconds, follow_redirects=True) as client:
            response = await client.get(
                endpoint,
                params={"q": query, "format": "jsonv2", "limit": 5, "addressdetails": 1},
                headers={
                    "User-Agent": f"{settings.app_name}/{settings.app_version} wildfire-geocoder",
                    "Accept-Language": "zh-CN,zh,en",
                },
            )
        _GEOCODE_LAST_REQUEST_AT = time.monotonic()
    response.raise_for_status()
    items = response.json()
    if not items:
        return {"ok": False, "reason": f"未找到地点：{location}", "query": query}
    item = items[0]
    longitude, latitude = float(item["lon"]), float(item["lat"])
    raw_bbox = item.get("boundingbox") or [latitude, latitude, longitude, longitude]
    south, north, west, east = (float(value) for value in raw_bbox)
    span_km = max(abs(north - south) * 111.0, abs(east - west) * 111.0 * max(0.25, math.cos(math.radians(latitude))))
    result = {
        "ok": True,
        "query": query,
        "display_name": str(item.get("display_name") or location),
        "longitude": longitude,
        "latitude": latitude,
        "bounding_box": [west, south, east, north],
        "camera_height_m": round(max(80000, min(2500000, span_km * 4000))),
        "place_type": str(item.get("type") or item.get("category") or "unknown"),
        "source": "OpenStreetMap Nominatim",
        "attribution": "© OpenStreetMap contributors",
        "cache_hit": False,
    }
    _GEOCODE_CACHE[cache_key] = (time.monotonic(), result)
    return result


@dataclass
class AssistantToolRuntime:
    db: AsyncSession
    trace: list[dict[str, Any]] = field(default_factory=list)
    location: dict[str, Any] | None = None
    region: dict[str, Any] | None = None
    sync_result: dict[str, Any] | None = None
    hotspot_result: dict[str, Any] | None = None
    event_result: dict[str, Any] | None = None
    readiness_result: dict[str, Any] | None = None

    async def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if len(self.trace) >= 12:
            return {"ok": False, "reason": "本轮工具调用已达到安全上限", "tool": name}
        try:
            result = await self._execute(name, arguments)
        except Exception as exc:
            result = {"ok": False, "reason": str(exc), "tool": name}
        self.trace.append({"tool": name, "arguments": arguments, "result": result})
        return result

    async def _execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "geocode_location":
            self.location = await geocode_location(
                str(arguments.get("location") or ""),
                str(arguments.get("country_hint") or ""),
            )
            return self.location
        if name == "select_realtime_region":
            self.region = select_region_for_point(float(arguments["longitude"]), float(arguments["latitude"]))
            return self.region
        if name == "sync_realtime_hotspots":
            payload = await sync_region(self.db, str(arguments["region_id"]))
            self.sync_result = {
                "ok": bool(payload.get("ready")),
                "region_id": payload.get("region_id"),
                "source": payload.get("source"),
                "observed_at": payload.get("observed_at"),
                "fetched_at": payload.get("fetched_at"),
                "total": int(payload.get("total") or 0),
                "cache_hit": bool(payload.get("cache_hit")),
                "data_source_mode": payload.get("data_source_mode"),
            }
            return self.sync_result
        if name == "query_hotspots_in_aoi":
            self.hotspot_result = await self._query_hotspots(
                str(arguments["region_id"]),
                float(arguments["longitude"]),
                float(arguments["latitude"]),
                max(5.0, min(500.0, float(arguments.get("radius_km") or 75.0))),
            )
            return self.hotspot_result
        if name == "find_events_near_location":
            self.event_result = await self._find_events(
                float(arguments["longitude"]),
                float(arguments["latitude"]),
                max(1.0, min(300.0, float(arguments.get("radius_km") or 75.0))),
            )
            return self.event_result
        if name == "check_data_readiness":
            event_id = str(arguments["event_id"])
            event = await self.db.scalar(select(FireEvent).where(FireEvent.event_id == event_id))
            self.readiness_result = (
                {"ok": True, **(await data_readiness(self.db, event_id))}
                if event is not None
                else {"ok": False, "reason": f"事件不存在：{event_id}"}
            )
            return self.readiness_result
        if name == "get_workflow_status":
            event_id = str(arguments["event_id"])
            run = await self.db.scalar(
                select(WorkflowRun).where(WorkflowRun.event_id == event_id).order_by(desc(WorkflowRun.created_at))
            )
            if run is None:
                return {"ok": True, "event_id": event_id, "status": "NOT_STARTED"}
            return {
                "ok": True,
                "event_id": event_id,
                "workflow_run_id": run.workflow_run_id,
                "status": run.status,
                "current_stage": run.current_stage,
                "human_confirmation_state": run.human_confirmation_state,
                "error": run.error,
            }
        return {"ok": False, "reason": f"未知工具：{name}"}

    async def _query_hotspots(
        self,
        region_id: str,
        longitude: float,
        latitude: float,
        radius_km: float,
    ) -> dict[str, Any]:
        observation = await self.db.scalar(
            select(RealtimeObservation)
            .where(RealtimeObservation.region_id == region_id)
            .order_by(desc(RealtimeObservation.fetched_at))
        )
        if observation is None:
            return {"ok": True, "region_id": region_id, "radius_km": radius_km, "total": 0, "items": [], "status": "NO_OBSERVATION"}
        latitude_delta = radius_km / 111.0
        longitude_delta = radius_km / (111.0 * max(0.2, math.cos(math.radians(latitude))))
        rows = (
            await self.db.scalars(
                select(RealtimeHotspot).where(
                    RealtimeHotspot.observation_id == observation.observation_id,
                    RealtimeHotspot.latitude.between(latitude - latitude_delta, latitude + latitude_delta),
                    RealtimeHotspot.longitude.between(longitude - longitude_delta, longitude + longitude_delta),
                )
            )
        ).all()
        matches = []
        for row in rows:
            distance = _distance_km(longitude, latitude, row.longitude, row.latitude)
            if distance <= radius_km:
                attributes = row.attributes or {}
                matches.append(
                    {
                        "detection_id": row.detection_id,
                        "observed_at": row.observed_at,
                        "longitude": row.longitude,
                        "latitude": row.latitude,
                        "distance_km": round(distance, 2),
                        "confidence": row.confidence,
                        "frp_mw": attributes.get("frp_mw"),
                        "status": row.status,
                    }
                )
        matches.sort(key=lambda item: (item["distance_km"], -float(item["confidence"] or 0)))
        return {
            "ok": True,
            "region_id": region_id,
            "observation_id": observation.observation_id,
            "source": observation.source,
            "observed_at": observation.observed_at,
            "fetched_at": observation.fetched_at,
            "radius_km": radius_km,
            "total": len(matches),
            "items": matches[:20],
            "status": "CANDIDATES_ONLY",
        }

    async def _find_events(self, longitude: float, latitude: float, radius_km: float) -> dict[str, Any]:
        events = (await self.db.scalars(select(FireEvent).order_by(desc(FireEvent.started_at)))).all()
        matches = []
        for event in events:
            distance = _distance_km(longitude, latitude, event.ignition_longitude, event.ignition_latitude)
            if distance <= radius_km:
                matches.append(
                    {
                        "event_id": event.event_id,
                        "name": event.name,
                        "distance_km": round(distance, 2),
                        "status": event.status,
                        "source_mode": event.source_mode,
                    }
                )
        matches.sort(key=lambda item: item["distance_km"])
        return {"ok": True, "radius_km": radius_km, "total": len(matches), "items": matches[:10]}


def _tool_system_prompt() -> str:
    return (
        "你是森林山火应急系统的工具调度 Agent。具体地点必须先调用 geocode_location，禁止凭记忆编坐标。"
        "获得坐标后依次调用 select_realtime_region、sync_realtime_hotspots、query_hotspots_in_aoi，"
        "并调用 find_events_near_location 判断系统是否已有独立事件。只有已有事件时才能检查数据就绪度和工作流。"
        "FIRMS 结果只能称为卫星热异常候选点，不能直接称为已确认山火。"
        "不得编造实时火点、天气、DEM、燃料、道路、资源、受灾面积或推演结果。"
        "区域不支持、接口失败或数据缺失时，必须如实返回限制。不要把 Dixie 数据用于其他地点。"
    )


def _json_for_model(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


async def _complete_required_location_steps(
    runtime: AssistantToolRuntime,
    location_hint: str | None,
) -> None:
    if (runtime.location is None or not runtime.location.get("ok")) and location_hint:
        await runtime.execute("geocode_location", {"location": location_hint})
    if not runtime.location or not runtime.location.get("ok"):
        return
    longitude = float(runtime.location["longitude"])
    latitude = float(runtime.location["latitude"])
    if runtime.region is None:
        await runtime.execute("select_realtime_region", {"longitude": longitude, "latitude": latitude})
    if runtime.event_result is None:
        await runtime.execute(
            "find_events_near_location",
            {"longitude": longitude, "latitude": latitude, "radius_km": 75},
        )
    if not runtime.region or not runtime.region.get("ok") or not runtime.region.get("supported"):
        return
    region_id = str(runtime.region["region_id"])
    if runtime.sync_result is None:
        await runtime.execute("sync_realtime_hotspots", {"region_id": region_id})
    if runtime.hotspot_result is None:
        await runtime.execute(
            "query_hotspots_in_aoi",
            {"region_id": region_id, "longitude": longitude, "latitude": latitude, "radius_km": 75},
        )
    nearby_events = (runtime.event_result or {}).get("items") or []
    if nearby_events and runtime.readiness_result is None:
        await runtime.execute("check_data_readiness", {"event_id": nearby_events[0]["event_id"]})


def _compose_grounded_response(runtime: AssistantToolRuntime, model_content: str) -> str:
    location = runtime.location or {}
    if not location.get("ok"):
        return model_content.strip() or f"无法完成地点定位：{location.get('reason', '请补充具体市县或经纬度')}。"
    name = location.get("display_name") or location.get("query") or "目标地点"
    region = runtime.region or {}
    prefix = f"已通过 {location.get('source', '地理编码服务')} 定位到{name}。"
    if not region.get("ok"):
        return prefix + f"{region.get('reason', '当前没有可用的实时监测区域')}，因此未声称获得当地实时火点。"
    if not region.get("supported"):
        return prefix + f"该地点位于“{region.get('label')}”，但此区域当前未启用实时同步，暂时不能给出真实候选火点。"
    hotspots = runtime.hotspot_result or {}
    sync = runtime.sync_result or {}
    if not hotspots.get("ok"):
        return prefix + f"FIRMS 查询失败：{hotspots.get('reason', '未知错误')}。"
    count = int(hotspots.get("total") or 0)
    observed = hotspots.get("observed_at") or sync.get("observed_at") or "未知"
    radius = hotspots.get("radius_km") or 75
    if count:
        hotspot_text = f"最近一次 FIRMS/VIIRS 观测在该地点 {radius:g} km 范围内发现 {count} 个卫星热异常候选点，观测时间为 {observed}。这些点尚不是已确认山火，必须继续进行遥感影像和人工核验。"
    else:
        hotspot_text = f"最近一次 FIRMS/VIIRS 观测在该地点 {radius:g} km 范围内未发现候选热异常点，观测时间为 {observed}；这不等于可以排除地面火情。"
    events = (runtime.event_result or {}).get("items") or []
    if events:
        event = events[0]
        readiness = runtime.readiness_result or {}
        missing = [item["name"] for item in readiness.get("items", []) if item.get("status") != "Available"]
        event_text = f"系统附近已有事件“{event['name']}”（{event['event_id']}）。"
        if missing:
            event_text += "运行完整推演前仍缺少：" + "、".join(missing) + "。"
    else:
        event_text = "系统尚未建立该地点的独立事件，也没有可直接用于推演的本地 DEM、燃料、逐时气象和应急资源数据。"
    return prefix + hotspot_text + event_text


async def run_general_wildfire_agent(
    message: str,
    context: dict[str, Any],
    db: AsyncSession,
    location_hint: str | None = None,
) -> dict[str, Any]:
    runtime = AssistantToolRuntime(db)
    provider = get_llm_provider()
    model_content = ""
    used_remote = False
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _tool_system_prompt()},
        {
            "role": "user",
            "content": _json_for_model(
                {
                    "request": message,
                    "current_system_context": context,
                    "location_hint": location_hint,
                    "instruction": "请调用工具获取真实证据；缺少地点时直接要求用户补充，不要猜测。",
                }
            ),
        },
    ]
    try:
        for _ in range(7):
            result = await provider.generate_with_tools(messages, ASSISTANT_TOOLS)
            used_remote = used_remote or result.used_remote
            if not result.tool_calls:
                model_content = result.content
                break
            messages.append(result.assistant_message)
            for call in result.tool_calls:
                tool_result = await runtime.execute(call.name, call.arguments)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.call_id,
                        "content": _json_for_model(tool_result),
                    }
                )
    except Exception as exc:
        model_content = f"模型工具调度暂不可用：{exc}"

    await _complete_required_location_steps(runtime, location_hint)
    if runtime.location is None:
        return {
            "message": model_content.strip() or "请补充要分析的具体市县、保护区或经纬度，我会先定位后查询真实 FIRMS 候选火点。",
            "source_mode": "tool_agent",
            "provider": provider.provider_name,
            "model": provider.model,
            "used_remote": used_remote,
            "tool_trace": runtime.trace,
        }
    data: dict[str, Any] = {
        "message": _compose_grounded_response(runtime, model_content),
        "source_mode": "tool_agent",
        "provider": provider.provider_name,
        "model": provider.model,
        "used_remote": used_remote,
        "tool_trace": runtime.trace,
        "evidence": {
            "location": runtime.location,
            "region": runtime.region,
            "hotspots": runtime.hotspot_result,
            "nearby_events": runtime.event_result,
            "readiness": runtime.readiness_result,
        },
    }
    if runtime.location.get("ok"):
        data["navigate_to"] = "/realtime-monitor"
        data["navigate_query"] = {
            "mode": "realtime",
            "focus": "location",
            "location": str(runtime.location.get("query") or ""),
            "lng": str(runtime.location["longitude"]),
            "lat": str(runtime.location["latitude"]),
            "height": str(runtime.location.get("camera_height_m") or 350000),
            **({"region": str(runtime.region["region_id"])} if runtime.region and runtime.region.get("ok") else {}),
        }
    return data


def extract_location_hint(message: str) -> str | None:
    patterns = (
        r"(?:分析|研判|评估|查看|关注|了解|查询|监测)\s*([^，。！？?]{2,40}?)(?:地区)?(?:的)?(?:森林)?(?:山火|火灾|火情)",
        r"(?:获取|查询|查看)\s*([^，。！？?]{2,40}?)(?:地区)?(?:的)?(?:实时|近实时)?(?:火点|热异常)",
    )
    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            value = re.sub(r"^(?:我想|请|帮我|现在|当前)", "", match.group(1)).strip()
            value = re.sub(r"(?:现在|当前|最近|今天)$", "", value).strip()
            if value in {"实时", "近实时", "当前", "现在", "全球", "全局", "世界范围"}:
                continue
            if value:
                return value
    return None
