# [Scene-Cache-Integration] WS 心跳协程
from __future__ import annotations

import asyncio
from typing import Any

from routers.websocket import manager


async def run_alert_heartbeat(scene_id: str, interval: int = 5) -> None:
    """向告警通道发送 mock 心跳，保持演示环境活跃。"""
    while True:
        payload: dict[str, Any] = {
            "type": "alert",
            "scene_id": scene_id,
            "message": "demo heartbeat",
            "status": "alive",
        }
        manager.update_uav_cache(f"heartbeat-{scene_id}", payload)
        await manager.broadcast(payload)
        await asyncio.sleep(interval)
