# [Scene-Cache-Integration] 前端友好初始化脚本
from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import websockets
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from models.registry import PersonnelRegistry, ResourceRegistry, UAVRegistry
from services.db_service import DBService
from services.scene_cache import get_scene_cache_value, set_scene_cache
from services.ws_heartbeat import run_alert_heartbeat


LOG_FILE = Path(__file__).resolve().parent / "seed.log"
DEFAULT_SCENE_ID = "seed-demo-001"
logger = logging.getLogger("seed_data")
logger.setLevel(logging.INFO)
logger.handlers.clear()
fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
for handler in (logging.StreamHandler(), logging.FileHandler(LOG_FILE, encoding="utf-8")):
    handler.setFormatter(fmt)
    logger.addHandler(handler)


async def seed_db(scene_id: str) -> dict[str, tuple[bool, bool]]:
    async with AsyncSessionLocal() as session:
        db = DBService(session)
        uavs = [{"id": 1, "name": "侦察鹰-1", "type": "inspection", "status": "idle", "scene_id": scene_id, "location": json.dumps({"lng": 114.31, "lat": 30.51, "alt": 100}, ensure_ascii=False), "last_update": datetime.now(timezone.utc)}]
        resources = [{"id": 1, "name": "重型水罐车", "type": "fire_truck", "status": "available", "scene_id": scene_id, "location": json.dumps({"lng": 114.29, "lat": 30.49}, ensure_ascii=False), "last_update": datetime.now(timezone.utc)}]
        personnel = [{"id": 1, "name": "张指挥", "type": "commander", "status": "on_duty", "scene_id": scene_id, "location": None, "last_update": datetime.now(timezone.utc)}]
        created_uav, updated_uav = await db.upsert_uav(uavs)
        created_res, updated_res = await db.upsert_resource(resources)
        created_per, updated_per = await db.upsert_personnel(personnel)
        return {"uav": (created_uav, updated_uav), "resource": (created_res, updated_res), "personnel": (created_per, updated_per)}


def build_scene_payload(scene_id: str, demo_safe: bool) -> dict[str, Any]:
    coords = [[114.30, 30.50], [114.31, 30.50], [114.32, 30.50]]
    fire_line = {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coords},
        "properties": {"scene_id": scene_id, "type": "fire_line", "step": 3, "popup": {"scene_id": scene_id, "type": "fire_line", "step": 3, "risk_hint": "火势向东蔓延"}},
    }
    return {
        "scene_id": scene_id,
        "current_step": 2,
        "fire_area": 0.85,
        "spread_speed": 1.2,
        "wind_params": {"wind_speed": 6.5, "wind_dir": 45},
        "risk_level": "high",
        "agent_summary": "火势向东蔓延，建议优先疏散东侧村庄",
        "current_fire_geojson": fire_line,
        "stats": {"current_step": 2, "fire_area": 0.85, "spread_speed": 1.2, "risk_level": "high"},
        "demo_safe": demo_safe,
    }


async def seed_cache(scene_id: str, demo_safe: bool, reset: bool = False) -> None:
    existing = get_scene_cache_value(scene_id)
    if existing and not reset:
        print("⚠️ 缓存已存在，跳过注入。使用 --reset 强制覆盖")
        return
    if reset:
        # [Scene-Cache-Integration] reset 强制覆盖缓存
        pass
    payload = build_scene_payload(scene_id, demo_safe)
    ttl = 0 if demo_safe else 600
    set_scene_cache(scene_id, payload, ttl=ttl)
    logger.info("已注入场景缓存 scene_id=%s ttl=%s", scene_id, ttl)


async def verify_http(path: str) -> None:
    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            resp = await client.get(path)
            body = resp.json()
            if resp.status_code == 200 and body.get("code") == 0 and body.get("data"):
                print(f"✅ {path} 验证通过")
            else:
                print(f"❌ {path} 验证失败: {body.get('message') or resp.text}")
        except Exception as exc:
            print(f"❌ {path} 验证失败: {exc}")


async def verify_ws() -> None:
    try:
        async with websockets.connect("ws://localhost:8100/ws/alert", ping_interval=None, close_timeout=1) as ws:
            await ws.recv()
            print("✅ ws://localhost:8100/ws/alert 验证通过")
    except Exception as exc:
        print(f"❌ ws://localhost:8100/ws/alert 验证失败: {exc}")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene-id", default=DEFAULT_SCENE_ID)
    parser.add_argument("--mock-only", action="store_true", default=True)
    parser.add_argument("--real", action="store_true")
    parser.add_argument("--activate-scene", action="store_true")
    parser.add_argument("--demo-safe", action="store_true")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    scene_id = args.scene_id
    if not args.real:
        await seed_cache(scene_id, demo_safe=args.demo_safe, reset=args.reset)
        if args.activate_scene:
            # [Scene-Cache-Integration] 演示激活，保持缓存活跃
            await run_alert_heartbeat(scene_id, interval=5)
            
    else:
        summary = await seed_db(scene_id)
        logger.info("真实DB写入结果: %s", summary)

    base = "http://127.0.0.1:8100"
    await verify_http(f"{base}/api/fire/list?scene_id={scene_id}")
    await verify_http(f"{base}/api/fire/stat?scene_id={scene_id}")
    await verify_http(f"{base}/api/uav/list")
    await verify_http(f"{base}/api/resource/list")
    await verify_http(f"{base}/api/personnel/list")
    await verify_ws()


if __name__ == "__main__":
    asyncio.run(main())

# 使用说明
# 默认：生成 scene_id=seed-demo-001 的完整Mock+缓存
# python scripts/seed_data.py
#
# 指定场景ID并自动验证
# python scripts/seed_data.py --scene-id=demo-01 --activate-scene
#
# 演示安全模式：缓存永不过期
# python scripts/seed_data.py --scene-id=demo-01 --demo-safe
#
# 写入真实DB（联调用）
# python scripts/seed_data.py --real --scene-id=prod-test
