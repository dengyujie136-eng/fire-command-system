from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import Base, engine
from models.registry import (
    DispatchActionLog,
    DispatchMaterialInventory,
    DispatchPersonnelInventory,
    DispatchUAVInventory,
)
from services.route_search import plan_point_to_point_route_options


DEFAULT_SCENE_ID = "forefire-default"


UAV_MISSION_TYPES = [
    ("firefighting", "灭火"),
    ("monitoring", "监测"),
    ("communication", "通信"),
    ("reconnaissance", "侦查"),
    ("transport", "运输"),
]


DEFAULT_MATERIALS = [
    ("fire_hose", "消防水管", "卷", 80, 40, 24),
    ("extinguisher", "灭火器", "具", 120, 50, 72),
    ("protective_suit", "防护服", "套", 80, 30, 48),
    ("first_aid_kit", "急救包", "包", 45, 20, 24),
    ("drinking_water", "饮用水", "box", 180, 80, 12),
    ("radio", "对讲机", "部", 50, 20, 24),
    ("fire_axe", "消防斧", "把", 36, 12, 168),
    ("portable_pump", "便携水泵", "台", 10, 4, 72),
    ("fuel_can", "油料桶", "桶", 30, 12, 24),
    ("lighting_tower", "移动照明设备", "台", 8, 3, 48),
]


DEFAULT_PERSONNEL = [
    ("北侧消防站", "firefighter", 18, {"lng": 101.242, "lat": 28.534}),
    ("南侧消防站", "firefighter", 12, {"lng": 101.292, "lat": 28.515}),
    ("县医院应急点", "medic", 8, {"lng": 101.279, "lat": 28.506}),
    ("现场指挥组", "commander", 3, {"lng": 101.265, "lat": 28.522}),
    ("后勤保障组", "logistics", 6, {"lng": 101.259, "lat": 28.518}),
]


DEFAULT_UAVS = [
    ("UAV-FIRE-01", "灭火无人机 01", "firefighting", {"lng": 101.258, "lat": 28.522}),
    ("UAV-FIRE-02", "灭火无人机 02", "firefighting", {"lng": 101.258, "lat": 28.522}),
    ("UAV-MON-01", "监测无人机 01", "monitoring", {"lng": 101.263, "lat": 28.526}),
    ("UAV-COM-01", "通信中继无人机 01", "communication", {"lng": 101.266, "lat": 28.524}),
    ("UAV-REC-01", "侦查无人机 01", "reconnaissance", {"lng": 101.261, "lat": 28.528}),
    ("UAV-TRANS-01", "运输无人机 01", "transport", {"lng": 101.255, "lat": 28.519}),
]


async def ensure_dispatch_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def generate_route_options(
    *,
    start: list[float] | None = None,
    end: list[float] | None = None,
    bbox: list[float] | None = None,
) -> list[dict[str, Any]]:
    if start is None:
        start = _default_start(bbox)
    if end is None:
        end = _default_end(bbox)

    return plan_point_to_point_route_options(
        start=start,
        end=end,
        fire_bbox=bbox,
        spread_direction="north",
    )


def build_operational_plan(
    decision: dict[str, Any],
    *,
    route_start: list[float] | None = None,
    route_end: list[float] | None = None,
) -> dict[str, Any]:
    summary = decision.get("input_summary", {})
    final_area = float(summary.get("final_area_km2", 0.0) or 0.0)
    risk_level = str(summary.get("risk_level") or "moderate")
    bbox = summary.get("final_bbox") if isinstance(summary.get("final_bbox"), list) else None
    recommended = decision.get("recommended_plan") or {}
    dispatch = decision.get("agent_outputs", {}).get("resource_dispatch", {})

    uav_tasks = _build_uav_tasks(risk_level, final_area, bbox)
    personnel_requirements = _build_personnel_requirements(risk_level, final_area)
    material_requirements = _build_material_requirements(risk_level, final_area)
    route_options = generate_route_options(start=route_start, end=route_end, bbox=bbox)

    return {
        "scene_id": decision.get("task_id") or DEFAULT_SCENE_ID,
        "recommended_plan_id": recommended.get("plan_id"),
        "uav_task_package": {
            "summary": "无人机当前以任务分配为主，路径可由 route_options 或后续坐标接口生成。",
            "tasks": uav_tasks,
        },
        "route_package": {
            "summary": "当前返回安全路径、中等路径、危险路径三类候选路径。前端后续传入起点/终点坐标后可重新规划。",
            "route_options": route_options,
        },
        "personnel_dispatch_package": {
            "requirements": personnel_requirements,
            "constraints": {
                "firefighter_total_limit_hint": 30,
                "reason": "默认周边两个消防站合计 30 名消防员，调度数量不得超过库存总量。",
            },
        },
        "material_dispatch_package": {
            "requirements": material_requirements,
            "maintenance_policy": {
                "monitoring_interval_hours": 12,
                "replace_consumables": ["drinking_water", "first_aid_kit", "radio_battery", "fuel_can"],
                "reason": "监测任务持续运行时，饮用水、急救包、通信电源和油料需要定期检查与补充。",
            },
        },
        "base_dispatch_tasks": dispatch.get("tasks", []),
    }


async def implement_operational_plan(
    db: AsyncSession,
    operational_plan: dict[str, Any],
    *,
    scene_id: str | None = None,
) -> dict[str, Any]:
    await ensure_dispatch_tables()
    scene_key = scene_id or operational_plan.get("scene_id") or DEFAULT_SCENE_ID
    await _seed_defaults_if_needed(db, scene_key)

    uav_result = await _assign_uavs(db, scene_key, operational_plan["uav_task_package"]["tasks"])
    personnel_result = await _dispatch_personnel(
        db,
        scene_key,
        operational_plan["personnel_dispatch_package"]["requirements"],
    )
    material_result = await _dispatch_materials(
        db,
        scene_key,
        operational_plan["material_dispatch_package"]["requirements"],
    )

    implemented_summary = {
        "scene_id": scene_key,
        "implemented_at": datetime.utcnow().isoformat(),
        "uav_assignments": uav_result["assignments"],
        "personnel_assignments": personnel_result["assignments"],
        "material_assignments": material_result["assignments"],
        "stock_warnings": material_result["stock_warnings"],
        "personnel_warnings": personnel_result["personnel_warnings"],
        "uav_warnings": uav_result["uav_warnings"],
    }
    db.add(
        DispatchActionLog(
            scene_id=scene_key,
            task_id=operational_plan.get("recommended_plan_id"),
            action_type="forefire_decision_implemented",
            summary="已默认实施 ForeFire 智能体生成的无人机、人员、物资调度方案，并更新资源库存。",
            payload=implemented_summary,
        )
    )
    await db.commit()

    current_state = await get_dispatch_state(db, scene_key)
    return {
        "implemented": True,
        "summary": implemented_summary,
        "current_state": current_state,
    }


async def get_dispatch_state(db: AsyncSession, scene_id: str | None = None) -> dict[str, Any]:
    await ensure_dispatch_tables()
    scene_key = scene_id or DEFAULT_SCENE_ID
    await _seed_defaults_if_needed(db, scene_key)

    materials = (await db.execute(select(DispatchMaterialInventory).where(DispatchMaterialInventory.scene_id == scene_key))).scalars().all()
    personnel = (await db.execute(select(DispatchPersonnelInventory).where(DispatchPersonnelInventory.scene_id == scene_key))).scalars().all()
    uavs = (await db.execute(select(DispatchUAVInventory).where(DispatchUAVInventory.scene_id == scene_key))).scalars().all()
    logs = (
        await db.execute(
            select(DispatchActionLog)
            .where(DispatchActionLog.scene_id == scene_key)
            .order_by(DispatchActionLog.created_at.desc())
            .limit(30)
        )
    ).scalars().all()

    return {
        "scene_id": scene_key,
        "materials": [_material_to_dict(row) for row in materials],
        "personnel": [_personnel_to_dict(row) for row in personnel],
        "uavs": [_uav_to_dict(row) for row in uavs],
        "actions": [_log_to_dict(row) for row in logs],
    }


async def _seed_defaults_if_needed(db: AsyncSession, scene_id: str) -> None:
    material_exists = (await db.execute(select(DispatchMaterialInventory).where(DispatchMaterialInventory.scene_id == scene_id).limit(1))).scalars().first()
    personnel_exists = (await db.execute(select(DispatchPersonnelInventory).where(DispatchPersonnelInventory.scene_id == scene_id).limit(1))).scalars().first()
    uav_exists = (await db.execute(select(DispatchUAVInventory).where(DispatchUAVInventory.scene_id == scene_id).limit(1))).scalars().first()

    if material_exists is None:
        for item_type, name, unit, quantity, threshold, cycle in DEFAULT_MATERIALS:
            db.add(
                DispatchMaterialInventory(
                    item_type=item_type,
                    name=name,
                    unit=unit,
                    total_quantity=quantity,
                    available_quantity=quantity,
                    reorder_threshold=threshold,
                    replacement_cycle_hours=cycle,
                    location=json.dumps({"lng": 101.255, "lat": 28.518}, ensure_ascii=False),
                    scene_id=scene_id,
                )
            )
    if personnel_exists is None:
        for station, role, count, location in DEFAULT_PERSONNEL:
            db.add(
                DispatchPersonnelInventory(
                    station_name=station,
                    role=role,
                    total_count=count,
                    available_count=count,
                    location=json.dumps(location, ensure_ascii=False),
                    scene_id=scene_id,
                )
            )
    if uav_exists is None:
        for uav_id, name, capability, location in DEFAULT_UAVS:
            db.add(
                DispatchUAVInventory(
                    uav_id=uav_id,
                    name=name,
                    capability=capability,
                    status="available",
                    battery_percent=92,
                    location=json.dumps(location, ensure_ascii=False),
                    scene_id=scene_id,
                )
            )
    if material_exists is None or personnel_exists is None or uav_exists is None:
        await db.commit()


def _build_uav_tasks(risk_level: str, final_area: float, bbox: list[float] | None) -> list[dict[str, Any]]:
    base_counts = {
        "firefighting": 2 if risk_level in {"high", "extreme"} else 1,
        "monitoring": 1,
        "communication": 1,
        "reconnaissance": 1,
        "transport": 1 if final_area >= 5 else 0,
    }
    tasks = []
    for capability, label in UAV_MISSION_TYPES:
        count = base_counts[capability]
        tasks.append(
            {
                "task_id": f"UAV-{capability.upper()}",
                "mission_type": capability,
                "mission_name": label,
                "required_uavs": count,
                "target": _uav_target(capability, bbox),
                "priority": "critical" if capability in {"firefighting", "communication"} else "high",
                "status": "planned" if count > 0 else "standby",
                "reason": _uav_reason(capability, risk_level),
                "route_planning": "当前不需要单独规划航线",
            }
        )
    return tasks


def _build_personnel_requirements(risk_level: str, final_area: float) -> list[dict[str, Any]]:
    firefighters = min(30, max(12, math.ceil(final_area * (2.4 if risk_level in {"high", "extreme"} else 1.6))))
    medics = min(8, max(2, math.ceil(firefighters / 8)))
    logistics = min(6, max(2, math.ceil(firefighters / 10)))
    commanders = 2 if risk_level in {"high", "extreme"} else 1
    return [
        {"role": "firefighter", "name": "消防员", "required_count": firefighters, "priority": "critical", "reason": "负责火线压制和重点目标保护。"},
        {"role": "medic", "name": "医疗员", "required_count": medics, "priority": "high", "reason": "负责现场急救和伤员转运准备。"},
        {"role": "commander", "name": "指挥员", "required_count": commanders, "priority": "high", "reason": "负责方案复核、现场安全边界和通信协调。"},
        {"role": "logistics", "name": "后勤保障人员", "required_count": logistics, "priority": "medium", "reason": "负责物资转运、水源保障和补给记录。"},
    ]


def _build_material_requirements(risk_level: str, final_area: float) -> list[dict[str, Any]]:
    factor = 1.25 if risk_level in {"high", "extreme"} else 1.0
    return [
        _material_req("fire_hose", "消防水管", math.ceil(final_area * 4.0 * factor), "卷", "critical"),
        _material_req("extinguisher", "灭火器", math.ceil(final_area * 5.0 * factor), "具", "high"),
        _material_req("protective_suit", "防护服", math.ceil(final_area * 3.0 * factor), "套", "critical"),
        _material_req("first_aid_kit", "急救包", math.ceil(final_area * 1.2 * factor), "包", "high"),
        _material_req("drinking_water", "饮用水", math.ceil(final_area * 6.0 * factor), "箱", "medium"),
        _material_req("radio", "对讲机", math.ceil(final_area * 1.0 * factor), "部", "high"),
        _material_req("fire_axe", "消防斧", math.ceil(final_area * 0.8 * factor), "把", "medium"),
        _material_req("portable_pump", "便携水泵", max(2, math.ceil(final_area / 3.5)), "台", "high"),
        _material_req("fuel_can", "油料桶", max(4, math.ceil(final_area * 1.2)), "桶", "medium"),
    ]


def _material_req(item_type: str, name: str, quantity: int, unit: str, priority: str) -> dict[str, Any]:
    return {
        "item_type": item_type,
        "name": name,
        "required_quantity": int(quantity),
        "unit": unit,
        "priority": priority,
        "reason": "根据火场面积、风险等级和持续监测补给需求估算。",
    }


async def _assign_uavs(db: AsyncSession, scene_id: str, tasks: list[dict[str, Any]]) -> dict[str, Any]:
    assignments = []
    warnings = []
    for task in tasks:
        required = int(task.get("required_uavs", 0) or 0)
        if required <= 0:
            continue
        result = await db.execute(
            select(DispatchUAVInventory)
            .where(
                DispatchUAVInventory.scene_id == scene_id,
                DispatchUAVInventory.capability == task["mission_type"],
                DispatchUAVInventory.status == "available",
            )
            .limit(required)
        )
        rows = result.scalars().all()
        if len(rows) < required:
            warnings.append(f"{task['mission_name']}无人机不足，需要 {required} 架，当前可用 {len(rows)} 架。")
        for row in rows:
            row.status = "assigned"
            row.last_update = datetime.utcnow()
            assignments.append(
                {
                    "task_id": task["task_id"],
                    "uav_id": row.uav_id,
                    "name": row.name,
                    "mission_type": task["mission_type"],
                    "mission_name": task["mission_name"],
                    "status": "assigned",
                }
            )
    await db.commit()
    return {"assignments": assignments, "uav_warnings": warnings}


async def _dispatch_personnel(db: AsyncSession, scene_id: str, requirements: list[dict[str, Any]]) -> dict[str, Any]:
    assignments = []
    warnings = []
    for req in requirements:
        required = int(req["required_count"])
        remaining = required
        rows = (
            await db.execute(
                select(DispatchPersonnelInventory)
                .where(
                    DispatchPersonnelInventory.scene_id == scene_id,
                    DispatchPersonnelInventory.role == req["role"],
                )
                .order_by(DispatchPersonnelInventory.available_count.desc())
            )
        ).scalars().all()
        total_available = sum(row.available_count for row in rows)
        if total_available < required:
            warnings.append(f"{req['name']}不足，需要 {required} 人，当前可用 {total_available} 人。")
        for row in rows:
            if remaining <= 0:
                break
            used = min(row.available_count, remaining)
            if used <= 0:
                continue
            row.available_count -= used
            row.last_update = datetime.utcnow()
            remaining -= used
            assignments.append(
                {
                    "role": req["role"],
                    "name": req["name"],
                    "station_name": row.station_name,
                    "assigned_count": used,
                    "remaining_available": row.available_count,
                    "status": "assigned",
                }
            )
    await db.commit()
    return {"assignments": assignments, "personnel_warnings": warnings}


async def _dispatch_materials(db: AsyncSession, scene_id: str, requirements: list[dict[str, Any]]) -> dict[str, Any]:
    assignments = []
    warnings = []
    for req in requirements:
        row = (
            await db.execute(
                select(DispatchMaterialInventory)
                .where(
                    DispatchMaterialInventory.scene_id == scene_id,
                    DispatchMaterialInventory.item_type == req["item_type"],
                )
                .limit(1)
            )
        ).scalars().first()
        if row is None:
            warnings.append(f"{req['name']}库存不存在，需要新增库存。")
            continue
        required = float(req["required_quantity"])
        used = min(row.available_quantity, required)
        row.available_quantity -= used
        row.last_update = datetime.utcnow()
        shortage = max(required - used, 0.0)
        need_restock = row.available_quantity <= row.reorder_threshold or shortage > 0
        if shortage > 0:
            warnings.append(f"{row.name}不足，缺口 {shortage:g} {row.unit}。")
        elif need_restock:
            warnings.append(f"{row.name}低于补库阈值，建议补充库存。")
        assignments.append(
            {
                "item_type": row.item_type,
                "name": row.name,
                "requested_quantity": required,
                "assigned_quantity": used,
                "shortage_quantity": shortage,
                "remaining_quantity": row.available_quantity,
                "unit": row.unit,
                "need_restock": need_restock,
                "replacement_cycle_hours": row.replacement_cycle_hours,
                "status": "assigned" if shortage == 0 else "partial",
            }
        )
    await db.commit()
    return {"assignments": assignments, "stock_warnings": warnings}


def _default_start(bbox: list[float] | None) -> list[float]:
    if bbox and len(bbox) == 4:
        return [round(bbox[0] - 0.015, 6), round(bbox[1] - 0.01, 6)]
    return [101.24, 28.515]


def _default_end(bbox: list[float] | None) -> list[float]:
    if bbox and len(bbox) == 4:
        return [round((bbox[0] + bbox[2]) / 2, 6), round(bbox[1] - 0.012, 6)]
    return [101.269444, 28.530278]


def _route_waypoints(start: list[float], end: list[float], factor: float, route_type: str) -> list[list[float]]:
    mid_lng = (start[0] + end[0]) / 2
    mid_lat = (start[1] + end[1]) / 2
    offset = 0.012 if route_type == "safe" else 0.006 if route_type == "medium" else -0.002
    if factor >= 1.4:
        return [start, [round(mid_lng - offset, 6), round(mid_lat - offset, 6)], [round(mid_lng + offset, 6), round(mid_lat - offset, 6)], end]
    if factor >= 1.1:
        return [start, [round(mid_lng, 6), round(mid_lat - offset, 6)], end]
    return [start, end]


def _distance_km(a: list[float], b: list[float]) -> float:
    mean_lat = math.radians((a[1] + b[1]) / 2)
    east = (b[0] - a[0]) * 111.320 * math.cos(mean_lat)
    north = (b[1] - a[1]) * 110.57669
    return math.sqrt(east * east + north * north)


def _uav_target(capability: str, bbox: list[float] | None) -> str:
    area = f"最终火场 bbox {bbox}" if bbox else "火场边界"
    return {
        "firefighting": f"{area}附近活动火线",
        "monitoring": f"{area}上空持续监测区",
        "communication": "现场指挥扇区上空临时通信中继点",
        "reconnaissance": f"{area}周边北、东、西侧扩张扇区",
        "transport": "安全营地与前线物资交接点",
    }.get(capability, area)


def _uav_reason(capability: str, risk_level: str) -> str:
    return {
        "firefighting": f"{_risk_label(risk_level)}需要空中灭火力量支援。",
        "monitoring": "持续监测火线变化和物资消耗状态。",
        "communication": "保障火场边缘与指挥中心通信。",
        "reconnaissance": "复核火线、烟羽和可通行区域。",
        "transport": "补充急救包、对讲机电池、饮用水等轻量物资。",
    }.get(capability, "支撑前线处置任务。")


def _risk_label(risk_level: str) -> str:
    return {
        "low": "低风险火情",
        "moderate": "中风险火情",
        "medium": "中风险火情",
        "high": "高风险火情",
        "extreme": "极高风险火情",
        "critical": "极高风险火情",
    }.get(str(risk_level), str(risk_level))


def _material_to_dict(row: DispatchMaterialInventory) -> dict[str, Any]:
    return {
        "id": row.id,
        "item_type": row.item_type,
        "name": row.name,
        "unit": row.unit,
        "total_quantity": row.total_quantity,
        "available_quantity": row.available_quantity,
        "reorder_threshold": row.reorder_threshold,
        "need_restock": row.available_quantity <= row.reorder_threshold,
        "replacement_cycle_hours": row.replacement_cycle_hours,
        "location": _parse_json(row.location),
        "scene_id": row.scene_id,
        "last_update": row.last_update.isoformat() if row.last_update else None,
    }


def _personnel_to_dict(row: DispatchPersonnelInventory) -> dict[str, Any]:
    return {
        "id": row.id,
        "station_name": row.station_name,
        "role": row.role,
        "total_count": row.total_count,
        "available_count": row.available_count,
        "assigned_count": row.total_count - row.available_count,
        "location": _parse_json(row.location),
        "scene_id": row.scene_id,
        "last_update": row.last_update.isoformat() if row.last_update else None,
    }


def _uav_to_dict(row: DispatchUAVInventory) -> dict[str, Any]:
    return {
        "id": row.id,
        "uav_id": row.uav_id,
        "name": row.name,
        "capability": row.capability,
        "status": row.status,
        "battery_percent": row.battery_percent,
        "location": _parse_json(row.location),
        "scene_id": row.scene_id,
        "last_update": row.last_update.isoformat() if row.last_update else None,
    }


def _log_to_dict(row: DispatchActionLog) -> dict[str, Any]:
    return {
        "id": row.id,
        "scene_id": row.scene_id,
        "task_id": row.task_id,
        "action_type": row.action_type,
        "summary": row.summary,
        "payload": row.payload,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _parse_json(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return value
