from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal, get_db
from routers.websocket import manager
from services.dispatch_state import (
    build_operational_plan,
    generate_route_options,
    get_dispatch_state,
    implement_operational_plan,
)
from services.environment_context import (
    build_environment_dem_input,
    build_environment_weather_input,
    load_local_environment_context,
)
from services.forefire_decision import (
    ForeFireDataError,
    generate_forefire_decision,
    load_forefire_input,
)
from services.resource_context import fetch_fire_demo_context, merge_decision_context


router = APIRouter(prefix="/api/agent/forefire", tags=["ForeFire Agent"])
ws_router = APIRouter(prefix="/ws/agent/forefire", tags=["ForeFire Agent WebSocket"])


class ForeFireDecisionRequest(BaseModel):
    type: str | None = None
    payload: dict[str, Any] | None = None
    event_id: str | None = None
    event_name: str | None = None
    ignition_point: dict[str, Any] | list[float] | None = None
    file_path: str | None = None
    forefire_json: dict[str, Any] | None = None
    scene_id: str | None = None
    weather: dict[str, Any] | None = None
    dem: dict[str, Any] | None = None
    environment_dir: str | None = None
    use_local_environment: bool = True
    resource_api_base_url: str | None = None
    fetch_resource_context: bool = True
    resources: dict[str, Any] | None = None
    targets: list[dict[str, Any]] | None = None
    include_coordinates: bool = False
    auto_implement: bool = True
    route_start: list[float] | None = None
    route_end: list[float] | None = None


class RoutePlanRequest(BaseModel):
    start: list[float]
    end: list[float]
    bbox: list[float] | None = None


@router.post("/decision", response_model=dict)
async def create_forefire_decision(
    request: ForeFireDecisionRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await _create_decision_from_body(
            request.model_dump(exclude_none=True),
            db,
            wrap_result=False,
            broadcast_updates=True,
        )
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ForeFireDataError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ForeFire 决策生成失败：{str(e)}")


@ws_router.websocket("/decision")
async def websocket_forefire_decision(websocket: WebSocket):
    await websocket.accept()
    try:
        await websocket.send_json(
            {
                "type": "progress",
                "status": "streaming",
                "message": "ForeFire 决策 WebSocket 已连接。",
                "payload": {},
            }
        )
        while True:
            message = await websocket.receive_json()
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong", "status": "ok", "payload": {}})
                continue
            if message.get("type") != "forefire_decision_request":
                await websocket.send_json(
                    {
                        "type": "error",
                        "status": "failed",
                        "message": "不支持的消息类型，请发送 forefire_decision_request。",
                        "payload": {},
                    }
                )
                continue

            async def send_progress(text: str, payload: dict[str, Any] | None = None) -> None:
                await websocket.send_json(
                    {
                        "type": "progress",
                        "status": "streaming",
                        "message": text,
                        "payload": payload or {},
                    }
                )

            try:
                async with AsyncSessionLocal() as db:
                    result = await _create_decision_from_body(
                        message,
                        db,
                        wrap_result=True,
                        broadcast_updates=False,
                        send_progress=send_progress,
                    )
                await websocket.send_json(result)
            except FileNotFoundError as e:
                await _send_ws_error(websocket, str(e))
            except ForeFireDataError as e:
                await _send_ws_error(websocket, str(e))
            except HTTPException as e:
                await _send_ws_error(websocket, str(e.detail))
            except Exception as e:
                await _send_ws_error(websocket, f"ForeFire 决策生成失败：{str(e)}")
    except WebSocketDisconnect:
        return
    except Exception:
        return


async def _send_ws_error(websocket: WebSocket, message: str) -> None:
    await websocket.send_json(
        {
            "type": "error",
            "status": "failed",
            "message": message,
            "payload": {},
        }
    )


async def _create_decision_from_body(
    body: dict[str, Any],
    db: AsyncSession,
    *,
    wrap_result: bool,
    broadcast_updates: bool,
    send_progress=None,
) -> dict[str, Any]:
    request = _normalize_decision_body(body)
    if send_progress:
        await send_progress("已收到 ForeFire 决策请求。")

    try:
        if request.get("forefire_json") is not None:
            payload = request["forefire_json"]
            source_path = request.get("file_path")
        elif request.get("file_path"):
            payload, source = load_forefire_input(request["file_path"])
            source_path = str(source)
        else:
            raise HTTPException(
                status_code=400,
                detail="请提供 forefire_json 或 file_path。",
            )

        if send_progress:
            await send_progress("ForeFire 数据已加载并完成校验。")

        environment_context = None
        if bool(request.get("use_local_environment", True)):
            environment_context = load_local_environment_context(request.get("environment_dir"))
            if send_progress:
                await send_progress("本地 DEM/Fuel/气象环境摘要已接入。")

        fetched_context = {"ok": False, "context": {}, "warnings": [], "source": None}
        if bool(request.get("fetch_resource_context", True)):
            fetched_context = fetch_fire_demo_context(base_url=request.get("resource_api_base_url"))
            if send_progress:
                status_text = "外部资源上下文已接入。" if fetched_context["ok"] else "外部资源上下文暂不可用，使用本地兜底资源。"
                await send_progress(status_text, {"source": fetched_context.get("source")})

        merged_context = merge_decision_context(request, fetched_context)
        weather_input = build_environment_weather_input(request.get("weather"), environment_context)
        dem_input = build_environment_dem_input(request.get("dem"), environment_context)

        result = generate_forefire_decision(
            payload,
            source_path=source_path,
            event_id=merged_context.get("event_id"),
            event_name=merged_context.get("event_name"),
            ignition_point=merged_context.get("ignition_point"),
            weather=weather_input,
            dem=dem_input,
            resources=merged_context.get("resources"),
            targets=merged_context.get("targets"),
            resource_context=merged_context.get("resource_context"),
            environment_context=environment_context,
            extra_warnings=merged_context.get("warnings"),
            include_coordinates=bool(request.get("include_coordinates", False)),
        )

        if send_progress:
            await send_progress("环境评估 Agent 已完成。")
            await send_progress("火势蔓延分析 Agent 已完成。")
            await send_progress("指挥决策 Agent 已完成。")

        scene_id = request.get("scene_id") or result["task_id"]
        operational_plan = build_operational_plan(
            result,
            route_start=request.get("route_start"),
            route_end=request.get("route_end"),
        )
        operational_plan["scene_id"] = scene_id

        result["agent_outputs"]["operational_dispatch"] = operational_plan
        result["packages"]["uav_task_package"] = operational_plan["uav_task_package"]
        result["packages"]["route_options_package"] = operational_plan["route_package"]
        result["packages"]["personnel_dispatch_package"] = operational_plan["personnel_dispatch_package"]
        result["packages"]["material_dispatch_package"] = operational_plan["material_dispatch_package"]

        if bool(request.get("auto_implement", True)):
            implementation = await implement_operational_plan(db, operational_plan, scene_id=scene_id)
            result["packages"]["implementation_package"] = implementation
            result["agent_outputs"]["implementation"] = implementation["summary"]
            if send_progress:
                await send_progress("资源调度 Agent 已完成，库存和调度状态已更新。")

        if broadcast_updates:
            await manager.broadcast(
                {
                    "type": "forefire_decision_generated",
                    "scene_id": scene_id,
                    "task_id": result["task_id"],
                    "status": result["status"],
                    "risk_level": result["input_summary"]["risk_level"],
                    "recommended_plan_id": result["recommended_plan"].get("plan_id"),
                    "generated_at": result["generated_at"],
                }
            )
            if bool(request.get("auto_implement", True)):
                await manager.broadcast(
                    {
                        "type": "dispatch_state_updated",
                        "scene_id": scene_id,
                        "task_id": result["task_id"],
                        "implementation": result["agent_outputs"]["implementation"],
                    }
                )

        if wrap_result:
            return {
                "type": "result",
                "status": result["status"],
                "payload": result,
            }
        return result
    except Exception:
        raise


def _normalize_decision_body(body: dict[str, Any]) -> dict[str, Any]:
    if isinstance(body.get("payload"), dict):
        normalized = dict(body["payload"])
        for key, value in body.items():
            if key not in {"type", "payload"} and key not in normalized:
                normalized[key] = value
        return normalized
    return dict(body)


@router.post("/route-plan", response_model=dict)
async def create_route_plan(request: RoutePlanRequest):
    try:
        routes = generate_route_options(start=request.start, end=request.end, bbox=request.bbox)
        await manager.broadcast(
            {
                "type": "route_plan_generated",
                "route_count": len(routes),
                "safe_route": routes[0] if routes else None,
            }
        )
        return {"status": "route_plan_generated", "route_options": routes}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"路径规划失败：{str(e)}")


@router.get("/dispatch/state", response_model=dict)
async def get_forefire_dispatch_state(
    scene_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    try:
        return {"status": "ok", "data": await get_dispatch_state(db, scene_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"调度状态查询失败：{str(e)}")
