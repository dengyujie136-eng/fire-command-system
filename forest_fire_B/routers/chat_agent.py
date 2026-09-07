from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from routers.frontend_data import ok
from services.flammap_registry import register_flammap_scene
from services.intent_router import classify_intent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["Agent Chat"])


class ChatRequest(BaseModel):
    scene_id: str
    question: str
    enable_vlm: bool = False


def _get_results_dir(scene_id: str) -> str:
    base_dir = os.getenv("FLAMMAP_DATA_DIR", "data/flammap_results")
    return str(Path(base_dir) / scene_id)


def _load_manifest(scene_id: str, results_dir: str) -> dict[str, Any]:
    cache_dir = Path("data") / "flammap_cache" / scene_id
    manifest_path = cache_dir / "manifest.json"
    if manifest_path.exists():
        with manifest_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return register_flammap_scene(scene_id=scene_id, results_dir=results_dir)


def _closest_time_key(available_times: list[str], target_key: str) -> str:
    if target_key in available_times:
        return target_key

    def _minutes(value: str) -> int:
        digits = "".join(ch for ch in value if ch.isdigit())
        return int(digits or "0")

    target_minutes = _minutes(target_key)
    return min(available_times, key=lambda x: abs(_minutes(x) - target_minutes))


@router.post("/chat")
async def chat_with_agent(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    try:
        _ = db  # 保留依赖注入，不改现有前端调用结构
        intent_result = classify_intent(request.question)
        results_dir = _get_results_dir(request.scene_id)
        manifest = _load_manifest(request.scene_id, results_dir)

        metadata = manifest.get("metadata", {})
        available_times = metadata.get("available_times", []) or []
        slices = manifest.get("slices", {}) or {}

        if intent_result["intent"] == "time_query":
            time_key = intent_result["time_key"] or (available_times[0] if available_times else "10m")
            if available_times:
                closest_time = _closest_time_key(available_times, time_key)
                layer_payload = slices.get(closest_time, {"type": "FeatureCollection", "features": []})
            else:
                closest_time = time_key
                layer_payload = {"type": "FeatureCollection", "features": []}
            answer = f"{closest_time}后的火灾蔓延范围如图所示。"
            timestamp = closest_time

        elif intent_result["intent"] == "risk_analysis":
            latest_time = available_times[-1] if available_times else "10m"
            layer_payload = slices.get(latest_time, {"type": "FeatureCollection", "features": []})
            answer = "根据蔓延趋势，当前最新时刻的下风向和边界扩展区域风险较高。"
            timestamp = latest_time

        elif intent_result["intent"] == "uav_route":
            layer_payload = {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [[114.3, 30.5], [114.31, 30.51], [114.32, 30.52]],
                        },
                        "properties": {"type": "uav_route", "scene_id": request.scene_id},
                    }
                ],
            }
            answer = "已生成无人机巡检航线，建议优先覆盖火场边界和下风向区域。"
            timestamp = intent_result["time_key"] or "route"

        elif intent_result["intent"] == "explanation":
            latest_time = available_times[-1] if available_times else "10m"
            layer_payload = slices.get(latest_time, {"type": "FeatureCollection", "features": []})
            answer = "这条结果说明当前火势在持续扩展，具体原因通常与风向、燃料和地形有关。"
            timestamp = latest_time

        else:
            latest_time = available_times[-1] if available_times else "10m"
            layer_payload = slices.get(latest_time, {"type": "FeatureCollection", "features": []})
            answer = "请具体描述您想了解的信息，例如“10分钟后火灾蔓延到哪里”。"
            timestamp = latest_time

        if request.enable_vlm and os.getenv("ENABLE_VLM", "false").lower() in {"1", "true", "yes", "on"}:
            answer = f"{answer}（VLM 解释已启用，但当前版本仍采用规则匹配作为主流程。）"

        return ok(
            data={
                "answer": answer,
                "ui_action": "show_layer",
                "layer_payload": layer_payload,
                "timestamp": timestamp,
                "intent": intent_result["intent"],
                "time_key": intent_result["time_key"],
                "scene_id": request.scene_id,
                "metadata": metadata,
            },
            scene_id=request.scene_id,
            intent=intent_result["intent"],
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("chat_with_agent failed")
        raise HTTPException(status_code=500, detail=f"chat failed: {str(e)}")
