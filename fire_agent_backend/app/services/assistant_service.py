from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.historical_event_service import query_historical_events
from app.services.review_service import build_disaster_review
from app.services.workflow_service import start_historical_fire_workflow


class AssistantChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    current_event_id: str | None = None
    current_historical_event_id: str | None = None
    page: str | None = None


ASSISTANT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "query_historical_fire_events",
            "description": "Query supported California historical fire events and rank them by a requested metric.",
            "parameters": {
                "type": "object",
                "properties": {
                    "last_years": {"type": "integer", "minimum": 1, "maximum": 50, "default": 5},
                    "sort_by": {"type": "string", "enum": ["burned_area_km2", "duration_days", "max_impact_area_km2"]},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "start_fire_workflow",
            "description": "Start the existing fire workflow for a locally supported historical event, including evidence, spread, risk, route, resources, Commander and report.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string"},
                    "include_report": {"type": "boolean", "default": True},
                },
                "required": ["event_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "start_disaster_review",
            "description": "Build disaster review analysis from registered event data, model outputs and explicit unavailable-data markers.",
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
            "name": "generate_report",
            "description": "Generate the existing downloadable command report for a completed fire workflow.",
            "parameters": {
                "type": "object",
                "properties": {"event_id": {"type": "string"}},
                "required": ["event_id"],
                "additionalProperties": False,
            },
        },
    },
]


def _format_event_candidate(item: Any) -> dict[str, Any]:
    return {
        "event_id": item.event_id,
        "name": item.name,
        "year": item.started_at.year,
        "region": item.region,
        "burned_area_km2": item.burned_area_km2,
        "duration_days": item.duration_days,
        "data_availability": item.data_availability,
        "source_mode": item.source_mode,
    }


def _intent(message: str) -> str:
    normalized = message.lower()
    if any(word in message for word in ['推演', '最大火灾', '过火面积', '近五年', '查询', '分析']) or any(word in normalized for word in ['simulate', 'forecast', 'largest', 'wildfire', 'fire event', 'spread', 'query', 'analyze']):
        return 'query_historical_fire'
    if any(word in message for word in ['复盘', '灾前', '灾后', '专题图', '报告']) or any(word in normalized for word in ['review', 'post-fire', 'pre-fire', 'report']):
        return 'review_event'
    return "general_status"


def _wants_workflow(message: str) -> bool:
    normalized = message.lower()
    return any(word in normalized for word in ["simulate", "forecast", "spread", "workflow"]) or (chr(0x63a8) + chr(0x6f14)) in message or (chr(0x706b) + chr(0x52bf)) in message

def _trace(name: str, status: str, **extra: Any) -> dict[str, Any]:
    return {"tool": name, "status": status, **extra}


async def _query_tool(db: AsyncSession, arguments: dict[str, Any]) -> dict[str, Any]:
    query = await query_historical_events(
        db,
        country="United States",
        region="California",
        last_years=int(arguments.get("last_years", 5)),
        sort_by=arguments.get("sort_by", "burned_area_km2"),
        limit=int(arguments.get("limit", 5)),
    )
    return {
        "query": query["query"],
        "retrieval_mode": query["retrieval_mode"],
        "events": [_format_event_candidate(item) for item in query["events"]],
    }


async def _run_tool(db: AsyncSession, name: str, arguments: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if name == "query_historical_fire_events":
        result = await _query_tool(db, arguments)
        return result, [_trace("DataAgent.query_historical_fire_events", "completed", result_count=len(result["events"]))]
    if name == "start_fire_workflow":
        result = await start_historical_fire_workflow(db, str(arguments["event_id"]), include_report=bool(arguments.get("include_report", True)))
        workflow = result["workflow"]
        summary = {
            "historical_event_id": result["historical_event_id"],
            "event_id": result["event"].event_id,
            "source_modes": result["source_modes"],
            "spread_run_id": getattr((workflow.get("spread") or {}).get("run"), "run_id", None),
            "report_id": getattr(workflow.get("report"), "report_id", None),
        }
        trace = [_trace("WorkflowAgent.start_fire_workflow", "completed", **summary)]
        if summary["report_id"]:
            trace.append(_trace("ReportAgent.generate_report", "completed", report_id=summary["report_id"]))
        return summary, trace
    if name == "start_disaster_review":
        result = await build_disaster_review(db, str(arguments["event_id"]))
        return result, [_trace("ReviewAgent.start_disaster_review", "completed", event_id=arguments["event_id"])]
    if name == "generate_report":
        result = await start_historical_fire_workflow(db, str(arguments["event_id"]), include_report=True)
        report = result["workflow"].get("report")
        summary = {
            "event_id": result["event"].event_id,
            "historical_event_id": result["historical_event_id"],
            "report_id": getattr(report, "report_id", None),
            "source_modes": result["source_modes"],
        }
        return summary, [_trace("ReportAgent.generate_report", "completed", **summary)]
    raise ValueError(f"Unsupported assistant tool: {name}")


def _remote_enabled() -> bool:
    return bool(get_settings().llm_api_key)


async def _remote_tool_calls(message: str, context: dict[str, Any]) -> tuple[list[dict[str, Any]], str, dict[str, Any]] | None:
    if not _remote_enabled():
        return None
    settings = get_settings()
    base_url = settings.llm_base_url or "https://open.bigmodel.cn/api/paas/v4"
    payload = {
        "model": settings.llm_model,
        "messages": [
            {
                "role": "system",
                "content": "You are a wildfire emergency assistant. Use only supplied tools for facts and actions. Never invent data. Prefer California historical events and preserve source modes.",
            },
            {"role": "user", "content": json.dumps({"message": message, "context": context}, ensure_ascii=False)},
        ],
        "tools": ASSISTANT_TOOLS,
        "tool_choice": "auto",
        "temperature": 0,
    }
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
    assistant_message = data.get("choices", [{}])[0].get("message", {})
    calls = []
    for item in assistant_message.get("tool_calls") or []:
        function = item.get("function") or {}
        if function.get("name"):
            calls.append({"name": function["name"], "arguments": json.loads(function.get("arguments") or "{}")})
    return calls, assistant_message.get("content") or "", {"provider": settings.llm_provider, "model": settings.llm_model}


async def _deterministic_tool_plan(request: AssistantChatRequest) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    intent = _intent(request.message)
    calls: list[dict[str, Any]] = []
    if intent == "review_event":
        event_id = request.current_historical_event_id or "dixie_fire_2021"
        calls.append({"name": "start_disaster_review", "arguments": {"event_id": event_id}})
        if "report" in request.message.lower() or (chr(0x62a5) + chr(0x544a)) in request.message:
            calls.append({"name": "generate_report", "arguments": {"event_id": event_id}})
    elif intent == "query_historical_fire":
        calls.append({"name": "query_historical_fire_events", "arguments": {"last_years": 5, "sort_by": "burned_area_km2", "limit": 5}})
    return calls, [_trace("DeterministicToolRouter", "completed", intent=intent)], {"provider": "none", "model": "deterministic-tool-router"}


async def run_assistant_chat(db: AsyncSession, request: AssistantChatRequest) -> dict[str, Any]:
    context = {"current_historical_event_id": request.current_historical_event_id, "page": request.page}
    remote = await _remote_tool_calls(request.message, context)
    if remote:
        calls, model_message, model_meta = remote
        llm_used = True
        trace = [_trace("LLM.function_calling", "completed", **model_meta)]
    else:
        calls, trace, model_meta = await _deterministic_tool_plan(request)
        model_message = ""
        llm_used = False

    results: list[dict[str, Any]] = []
    selected_event: dict[str, Any] | None = None
    actions: list[dict[str, Any]] = []
    for call in calls:
        try:
            result, call_trace = await _run_tool(db, call["name"], call.get("arguments") or {})
            results.append({"tool": call["name"], "result": result})
            trace.extend(call_trace)
            if call["name"] == "start_fire_workflow":
                actions.append({"type": "hydrate_workflow", "route": "/command-center", **result})
            elif call["name"] == "start_disaster_review":
                actions.append({"type": "navigate", "route": "/disaster-review", "query": {"event_id": call.get("arguments", {}).get("event_id")}})
            elif call["name"] == "generate_report":
                actions.append({"type": "hydrate_workflow", "route": "/command-center", **result})
            if call["name"] == "query_historical_fire_events":
                selected_event = (result.get("events") or [None])[0]
                if selected_event and _wants_workflow(request.message):
                    event_id = selected_event["event_id"]
                    workflow_result, workflow_trace = await _run_tool(db, "start_fire_workflow", {"event_id": event_id, "include_report": any(word in request.message for word in ["报告", "复盘"]) or any(word in request.message.lower() for word in ["report", "review"])})
                    results.append({"tool": "start_fire_workflow", "result": workflow_result})
                    trace.extend(workflow_trace)
                    actions.append({"type": "hydrate_workflow", "route": "/command-center", **workflow_result})
                if selected_event and any(word in request.message for word in ["复盘", "灾前", "灾后", "专题图", "review", "post-fire", "pre-fire"]):
                    event_id = selected_event["event_id"]
                    review_result, review_trace = await _run_tool(db, "start_disaster_review", {"event_id": event_id})
                    results.append({"tool": "start_disaster_review", "result": {"event": review_result["event"], "source_modes": review_result["source_modes"]}})
                    trace.extend(review_trace)
                    actions.append({"type": "navigate", "route": "/disaster-review", "query": {"event_id": event_id}})
        except Exception as exc:
            trace.append(_trace(call["name"], "failed", error=exc.__class__.__name__))
            results.append({"tool": call["name"], "error": str(exc)})

    if not selected_event:
        for item in results:
            if item["tool"] == "query_historical_fire_events":
                selected_event = (item.get("result", {}).get("events") or [None])[0]

    if actions:
        message = "工具链已执行，页面将加载后端产生的事件、推演、风险、路线、资源、Commander 与复盘结果。"
    elif selected_event:
        message = f"已从 California 历史事件库按过火面积返回候选，最大候选为 {selected_event['name']} ({selected_event['year']})。"
    elif model_message:
        message = model_message
    else:
        message = "当前可用工具包括历史事件查询、综合推演、灾前灾后复盘和报告生成。"

    return {
        "schema_version": "fire.assistant.chat.v0.2",
        "intent": _intent(request.message),
        "llm_used": llm_used,
        "llm_provider": model_meta["provider"],
        "llm_model": model_meta["model"],
        "message": message,
        "selected_event": selected_event,
        "tool_trace": trace,
        "tool_results": results,
        "actions": actions,
        "source_modes": {
            "assistant_routing": "llm_tool_calling" if llm_used else "deterministic_tool_router",
            "event_catalog": "real_data",
            "workflow": "model_result_or_drill_data_by_stage",
        },
    }
