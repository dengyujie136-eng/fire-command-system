# routers/agent.py
import os
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from autogen_agentchat.agents import AssistantAgent
    from autogen_agentchat.messages import TextMessage
    from autogen_ext.models.openai import OpenAIChatCompletionClient
    from autogen_ext.models.ollama import OllamaChatCompletionClient
except Exception:  # pragma: no cover - runtime fallback for missing optional deps
    AssistantAgent = None
    TextMessage = None
    OpenAIChatCompletionClient = None
    OllamaChatCompletionClient = None

from clients.c_client import call_c_simulate
from database import get_db
from services.agent_runtime import AgentLoopManager, run_agent_cycle

router = APIRouter(
    prefix="/agent",
    tags=["agent"],
)
loop_manager = AgentLoopManager()

AGENT_MODEL_PROVIDER = os.getenv("AGENT_MODEL_PROVIDER", "mimo_api").lower()
AGENT_MODEL = os.getenv("AGENT_MODEL", "MiMo-V2.5-Pro")
AGENT_API_BASE_URL = os.getenv("AGENT_API_BASE_URL", "https://api.xiaomimimo.com/v1")
AGENT_API_KEY = os.getenv("AGENT_API_KEY") or os.getenv("MIMO_API_KEY")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "alibayram/mimo-7b-rl")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")

model_client = None
fire_analysis_agent = None
simulation_report_agent = None
dispatch_planner_agent = None
drone_planner_agent = None
if AssistantAgent:
    if AGENT_MODEL_PROVIDER in {"mimo_api", "openai_compatible", "openai"} and OpenAIChatCompletionClient:
        if AGENT_API_KEY:
            model_client = OpenAIChatCompletionClient(
                model=AGENT_MODEL,
                base_url=AGENT_API_BASE_URL,
                api_key=AGENT_API_KEY,
                model_info={
                    "vision": False,
                    "function_calling": False,
                    "json_output": False,
                    "family": "unknown",
                    "structured_output": False,
                },
            )
    elif AGENT_MODEL_PROVIDER == "ollama" and OllamaChatCompletionClient:
        model_client = OllamaChatCompletionClient(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
        )

if model_client and AssistantAgent:
    fire_analysis_agent = AssistantAgent(
        name="FireAnalysisExpert",
        model_client=model_client,
        system_message=(
            "你是一位森林火灾分析专家。"
            "根据提供的火点位置、风速、风向，分析火势蔓延趋势，给出简要的疏散建议。"
            "请用中文回答。"
        ),
    )

    simulation_report_agent = AssistantAgent(
        name="SimulationReportExpert",
        model_client=model_client,
        system_message=(
            "你是一位应急指挥中心的推演报告撰写专家。"
            "你将收到火灾模拟的火线数据（GeoJSON格式）以及气象条件。"
            "请根据这些数据，撰写一份简短的《火势推演报告》，包含：当前态势、预计蔓延方向、关键风险点。"
            "请用中文回答，格式清晰。"
        ),
    )

    dispatch_planner_agent = AssistantAgent(
        name="DispatchPlanner",
        model_client=model_client,
        system_message=(
            "你是森林火灾资源调度专家。"
            "请根据火场面积、风场变化和事件触发信息，输出消防车/无人机/消防员数量建议。"
            "输出要求务实简洁，给出调度原因。"
        ),
    )

    drone_planner_agent = AssistantAgent(
        name="DronePlanner",
        model_client=model_client,
        system_message=(
            "你是无人机任务规划专家。"
            "请根据火点、风向、风险事件给出巡检策略。"
            "重点说明应优先关注的方向与覆盖范围建议。"
        ),
    )


def _is_agent_runtime_ready() -> bool:
    return fire_analysis_agent is not None and simulation_report_agent is not None


class AnalysisRequest(BaseModel):
    fire_point: list[float]  # [lng, lat]
    wind_speed: float
    wind_dir: int
    terrain: str = "local_dem"
    steps: int = 12
    sentinel_client_id: str | None = None
    sentinel_client_secret: str | None = None


class DronePlanRequest(BaseModel):
    fire_point: list[float]
    area_range: float = 5.0


class AgentCycleRequest(BaseModel):
    scene_id: str
    wind_speed: Optional[float] = None
    wind_dir: Optional[float] = None


class AgentLoopStartRequest(BaseModel):
    scene_id: str
    interval_seconds: int = 30
    max_cycles: int = 0


async def call_simulate_api(request: AnalysisRequest) -> dict:
    return await call_c_simulate(
        {
            "fire_point": request.fire_point,
            "wind_speed": request.wind_speed,
            "wind_dir": request.wind_dir,
            "terrain": request.terrain,
            "steps": request.steps,
            "sentinel_client_id": request.sentinel_client_id,
            "sentinel_client_secret": request.sentinel_client_secret,
        }
    )


def generate_mock_drone_route(fire_point: list, range_km: float) -> List[Dict]:
    lon, lat = fire_point
    offset = range_km * 0.01

    return [
        {"lat": lat - offset, "lon": lon - offset, "alt": 100},
        {"lat": lat + offset, "lon": lon - offset, "alt": 120},
        {"lat": lat + offset, "lon": lon + offset, "alt": 150},
        {"lat": lat - offset, "lon": lon + offset, "alt": 120},
        {"lat": lat, "lon": lon, "alt": 200},
    ]


async def _run_analysis_text(context: Dict[str, Any]) -> str:
    if not _is_agent_runtime_ready():
        trend = "高风险快速蔓延" if context["wind_speed"] >= 10 else "中低速蔓延"
        return (
            f"当前态势：{trend}，风速{context['wind_speed']}m/s，风向{context['wind_dir']}度。"
            f"估算火场面积{context['fire_area']}，建议优先巡检下风向区域并准备重规划。"
        )

    task_prompt = (
        f"你是森林火灾分析专家。请基于以下态势给出简明分析和建议：\n"
        f"- scene_id: {context['scene_id']}\n"
        f"- step: {context['step']}\n"
        f"- fire_point: {context['fire_point']}\n"
        f"- wind_speed: {context['wind_speed']} m/s\n"
        f"- wind_dir: {context['wind_dir']} 度\n"
        f"- fire_area: {context['fire_area']}\n"
        f"请输出：1) 当前风险等级；2) 关键风险点；3) 下一步建议。"
    )
    result = await fire_analysis_agent.run(task=task_prompt)
    if not result.messages:
        return "未获取到有效分析，建议保持当前部署并继续监测。"
    last_message = result.messages[-1]
    if TextMessage is not None and isinstance(last_message, TextMessage):
        return str(last_message.content)
    return str(last_message.content)


async def _run_dispatch_worker(context: Dict[str, Any]) -> Dict[str, Any]:
    area = float(context["fire_area"])
    need_replan = bool(context["need_replan"])
    events = context.get("events", [])

    base_plan = {
        "fire_trucks": max(1, int(area / 2) + 1),
        "uavs": max(1, int(area / 5) + 1),
        "firefighters": max(3, (max(1, int(area / 2) + 1)) * 3),
        "dispatch_reason": "event_triggered_replan" if need_replan else "routine_cycle",
    }

    if dispatch_planner_agent is None or not _is_agent_runtime_ready():
        return base_plan

    task_prompt = (
        f"请给出资源调度建议：\n"
        f"- scene_id: {context['scene_id']}\n"
        f"- fire_area: {context['fire_area']}\n"
        f"- wind_speed: {context['wind_speed']}\n"
        f"- events: {events}\n"
        f"请返回紧凑建议文本。"
    )
    result = await dispatch_planner_agent.run(task=task_prompt)
    if result.messages:
        last_message = result.messages[-1]
        base_plan["llm_advice"] = str(last_message.content)
    return base_plan


async def _run_drone_worker(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    fire_point = context["fire_point"]
    need_replan = bool(context["need_replan"])
    base_route = generate_mock_drone_route(fire_point=fire_point, range_km=5.0 if need_replan else 3.0)

    if drone_planner_agent is None or not _is_agent_runtime_ready():
        return base_route

    task_prompt = (
        f"请基于以下态势给出无人机巡检重点建议：\n"
        f"- scene_id: {context['scene_id']}\n"
        f"- fire_point: {context['fire_point']}\n"
        f"- wind_dir: {context['wind_dir']}\n"
        f"- events: {context.get('events', [])}\n"
        f"请输出一段简短建议。"
    )
    result = await drone_planner_agent.run(task=task_prompt)
    if result.messages:
        last_message = result.messages[-1]
        # 把 worker 建议挂到最后一个航点，便于前端快速展示
        base_route[-1]["advice"] = str(last_message.content)
    return base_route


@router.post("/analyze", response_model=Dict[str, str])
async def analyze_fire(request: AnalysisRequest):
    try:
        if not _is_agent_runtime_ready():
            return {"analysis": "当前环境未安装 AutoGen 依赖，已降级为基础模式。请先安装 autogen_agentchat/autogen_ext 后启用智能体分析。"}

        lng, lat = request.fire_point
        task_prompt = (
            f"当前火情数据如下：\n"
            f"- 火点坐标: 经度 {lng}, 纬度 {lat}\n"
            f"- 风速: {request.wind_speed} m/s\n"
            f"- 风向: {request.wind_dir} 度\n"
            f"请分析火势蔓延趋势并给出疏散建议。"
        )

        result = await fire_analysis_agent.run(task=task_prompt)
        if result.messages:
            last_message = result.messages[-1]
            analysis_text = (
                last_message.content
                if TextMessage is not None and isinstance(last_message, TextMessage)
                else str(last_message.content)
            )
        else:
            analysis_text = "Agent 未返回有效分析结果。"

        return {"analysis": analysis_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent 分析失败: {str(e)}")


@router.post("/loop/step", response_model=Dict[str, Any])
async def run_agent_single_cycle(
    request: AgentCycleRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    执行一轮感知-分析-规划-行动闭环。
    """
    try:
        state = await run_agent_cycle(
            db=db,
            scene_id=request.scene_id,
            analysis_worker_fn=_run_analysis_text,
            dispatch_worker_fn=_run_dispatch_worker,
            drone_worker_fn=_run_drone_worker,
            override_wind_speed=request.wind_speed,
            override_wind_dir=request.wind_dir,
        )
        return {"message": "single cycle completed", "state": state}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"single cycle failed: {str(e)}")


@router.post("/loop/start", response_model=Dict[str, Any])
async def start_agent_loop(request: AgentLoopStartRequest):
    """
    启动持续闭环（事件驱动可在下一步接入；当前版本为定时循环）。
    """
    try:
        interval = max(5, int(request.interval_seconds))
        max_cycles = max(0, int(request.max_cycles))
        status = await loop_manager.start(
            scene_id=request.scene_id,
            interval_seconds=interval,
            max_cycles=max_cycles,
            analysis_worker_fn=_run_analysis_text,
            dispatch_worker_fn=_run_dispatch_worker,
            drone_worker_fn=_run_drone_worker,
        )
        return {"message": "loop started", "status": status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"start loop failed: {str(e)}")


@router.post("/loop/stop/{scene_id}", response_model=Dict[str, Any])
async def stop_agent_loop(scene_id: str):
    try:
        stopped = await loop_manager.stop(scene_id)
        return {"scene_id": scene_id, "stopped": stopped}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"stop loop failed: {str(e)}")


@router.get("/loop/status/{scene_id}", response_model=Dict[str, Any])
async def get_agent_loop_status(scene_id: str):
    try:
        return loop_manager.status(scene_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"status query failed: {str(e)}")


@router.post("/simulate", response_model=Dict[str, Any])
async def agent_simulate(request: AnalysisRequest):
    """
    推演 Agent：
    1. 走 C 的 V1 链路获取火线数据
    2. 让 Agent 生成推演报告
    3. 返回报告 + 原始火线数据
    """
    try:
        if not _is_agent_runtime_ready():
            sim_result = await call_simulate_api(request)
            return {
                "report": "当前环境未安装 AutoGen 依赖，已返回基础推演数据。",
                "incident_id": sim_result.get("incident_id"),
                "simulation_id": sim_result.get("simulation_id"),
                "fire_lines": sim_result.get("result", {}).get("fire_lines", []),
            }

        sim_result = await call_simulate_api(request)
        fire_lines = sim_result.get("result", {}).get("fire_lines", [])
        if not isinstance(fire_lines, list):
            fire_lines = []

        prompt_detail = f"模拟显示共有 {len(fire_lines)} 个时间步的火线变化。"
        task_prompt = (
            f"基于以下火灾模拟结果生成推演报告：\n"
            f"- 火点: {request.fire_point}\n"
            f"- 气象: 风速 {request.wind_speed}m/s, 风向 {request.wind_dir}度\n"
            f"- 模拟详情: {prompt_detail}\n"
            f"请生成报告。"
        )

        result = await simulation_report_agent.run(task=task_prompt)
        report_text = ""
        if result.messages:
            last_message = result.messages[-1]
            report_text = (
                last_message.content
                if TextMessage is not None and isinstance(last_message, TextMessage)
                else str(last_message.content)
            )

        return {
            "report": report_text,
            "incident_id": sim_result.get("incident_id"),
            "simulation_id": sim_result.get("simulation_id"),
            "fire_lines": fire_lines,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"推演失败: {str(e)}")


@router.post("/drone-plan", response_model=Dict[str, Any])
async def plan_drone_mission(request: DronePlanRequest):
    try:
        route = generate_mock_drone_route(request.fire_point, request.area_range)
        return {
            "message": f"已为火点 {request.fire_point} 生成勘察航线，共 {len(route)} 个航点，覆盖范围 {request.area_range}km。",
            "route": route,
            "total_points": len(route),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"无人机规划失败: {str(e)}")
