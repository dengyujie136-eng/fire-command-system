from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


DEFAULT_EVENT_ID = "muli-fire-demo-001"
DEFAULT_EVENT_NAME = "木里县森林火灾演示事件"
DEFAULT_IGNITION_POINT = {"longitude": 101.269444, "latitude": 28.530278}
DEFAULT_RESOURCE_API_BASE_URL = "http://localhost:5000"


def fetch_fire_demo_context(
    *,
    base_url: str | None = None,
    timeout_seconds: float = 1.5,
) -> dict[str, Any]:
    selected_base_url = (base_url or os.getenv("RESOURCE_API_BASE_URL") or DEFAULT_RESOURCE_API_BASE_URL).rstrip("/") + "/"
    endpoint = urljoin(selected_base_url, "api/context/fire-demo")
    request = Request(endpoint, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8-sig")
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError("资源上下文接口返回内容不是 JSON 对象。")
        return {
            "ok": True,
            "source": endpoint,
            "context": payload,
            "warnings": [],
        }
    except (OSError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        return {
            "ok": False,
            "source": endpoint,
            "context": {},
            "warnings": [f"外部资源上下文读取失败，已使用本地默认资源兜底：{exc}"],
        }


def merge_decision_context(
    request: dict[str, Any],
    fetched_context: dict[str, Any] | None,
) -> dict[str, Any]:
    context = dict((fetched_context or {}).get("context") or {})
    warnings = list((fetched_context or {}).get("warnings") or [])

    event_id = str(request.get("event_id") or context.get("event_id") or DEFAULT_EVENT_ID)
    event_name = str(request.get("event_name") or context.get("event_name") or DEFAULT_EVENT_NAME)
    ignition_point = request.get("ignition_point") or context.get("ignition_point") or DEFAULT_IGNITION_POINT

    resources = _merge_resource_payload(request.get("resources"), context)
    targets = request.get("targets")
    if targets is None:
        targets = context.get("important_targets")

    return {
        "event_id": event_id,
        "event_name": event_name,
        "ignition_point": ignition_point,
        "resources": resources,
        "targets": targets,
        "resource_context": context,
        "resource_context_source": (fetched_context or {}).get("source"),
        "resource_context_loaded": bool((fetched_context or {}).get("ok")),
        "warnings": warnings,
    }


def _merge_resource_payload(
    request_resources: dict[str, Any] | None,
    context: dict[str, Any],
) -> dict[str, Any] | None:
    if request_resources and not context:
        return request_resources
    if not request_resources and not context:
        return None

    merged = dict(request_resources or {})
    for key in (
        "resource_inventory",
        "personnel_units",
        "uav_assets",
        "vehicles",
        "water_sources",
        "shelters",
        "important_targets",
        "road_segments",
    ):
        if key in context and key not in merged:
            merged[key] = context[key]

    if context:
        merged.setdefault("event_id", context.get("event_id"))
        merged.setdefault("event_name", context.get("event_name"))
        merged.setdefault("source", "resource_api_context")
    return merged
