import re
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/assistant", tags=["assistant"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    page: str = ""
    context: dict[str, Any] = Field(default_factory=dict)


PAGES = {
    "监测": "/realtime-monitor",
    "核验": "/visual-verification",
    "推演": "/command-center",
    "规划": "/planning",
    "评估": "/disaster-assess",
}




def _requested_horizon(message: str) -> int | None:
    match = re.search(r"([0-9一二三四五六七八九十两]+)\s*(?:个)?\s*小时\s*(?:之后|以后|后)", message)
    if match is None:
        match = re.search(r"(?:推演|预测)\s*([0-9一二三四五六七八九十两]+)\s*(?:个)?\s*小时", message)
    if match is None:
        minute_match = re.search(r"(?:推演|预测)\s*(\d{2,4})\s*分钟", message)
        if minute_match:
            minutes = int(minute_match.group(1))
            return minutes if 60 <= minutes <= 1440 else None
        return None
    raw = match.group(1)
    values = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6,
              "七": 7, "八": 8, "九": 9, "十": 10}
    if raw.isdigit():
        hours = int(raw)
    elif raw in values:
        hours = values[raw]
    elif len(raw) == 2 and raw.startswith("十") and raw[1] in values:
        hours = 10 + values[raw[1]]
    elif len(raw) == 3 and raw[1] == "十" and raw[0] in values and raw[2] in values:
        hours = values[raw[0]] * 10 + values[raw[2]]
    else:
        return None
    return hours * 60 if 1 <= hours <= 24 else None


def _weather_overrides(message: str) -> dict[str, float]:
    values: dict[str, float] = {}
    patterns = {
        "wind_speed_m_s": r"风速(?:改为|改成|设为|设置为|是|为)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m/s|米/秒|米每秒)?",
        "wind_direction_deg": r"风向(?:改为|改成|设为|设置为|是|为)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:°|度)?",
        "temperature_c": r"(?:温度|气温)(?:改为|改成|设为|设置为|是|为)?\s*(-?[0-9]+(?:\.[0-9]+)?)\s*(?:℃|°C|度)?",
        "humidity_percent": r"(?:湿度|相对湿度)(?:改为|改成|设为|设置为|是|为)?\s*([0-9]+(?:\.[0-9]+)?)\s*%?",
    }
    limits = {"wind_speed_m_s": (0, 60), "wind_direction_deg": (0, 359.999),
              "temperature_c": (-30, 65), "humidity_percent": (0, 100)}
    for name, pattern in patterns.items():
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            low, high = limits[name]
            if low <= value <= high:
                values[name] = value
    return values


@router.post("/chat")
async def chat(request: ChatRequest) -> dict[str, Any]:
    message = request.message.strip()
    weather = _weather_overrides(message)
    context = {key: request.context.get(key) for key in (
        "event_id", "event_name", "mode", "workflow_status", "current_stage",
        "confirmed", "spread_run_id", "route_plan_id", "resource_plan_id"
    )}
    # Return explicit commands. The browser executes them against the existing
    # workflow/data endpoints and reports the persisted result, including human gates.
    needs_imagery = any(word in message for word in ("影像", "遥感", "卫星", "数据获取", "下载"))
    needs_verify = any(word in message for word in ("核验", "火点检测", "候选火点", "识别火点"))
    needs_spread = any(word in message for word in ("推演", "推理", "蔓延", "预测"))
    needs_plan = any(word in message for word in ("规划", "调度", "路径", "路线"))
    needs_assessment = any(word in message for word in ("灾前灾后", "灾后评估", "重建建议"))
    complete = any(word in message for word in ("完整", "整个工作流", "全流程")) and needs_spread
    multi_stage = sum((needs_imagery, needs_verify, needs_spread, needs_plan)) >= 2
    if complete or multi_stage:
        horizon = _requested_horizon(message) or 240
        return {"ok": True, "data": {
            "message": "正在创建历史火灾工作流；数据检查、候选火点、核验、推演和规划将按真实阶段运行。影像或人工确认缺失时会暂停并显示原因。",
            "navigate_to": "/visual-verification",
            "action": {"type": "start_workflow", "event_id": "dixie_fire_2021" if "Dixie" in message or "迪克西" in message else context.get("event_id") or "dixie_fire_2021", "horizon_minutes": horizon, "acquire_imagery": needs_imagery or complete},
            "source_mode": "structured",
        }}
    if needs_assessment:
        return {"ok": True, "data": {
            "message": "正在检查灾前和灾后影像目录；两期五波段产品就绪后将运行真实变化检测，并调用 Qwen-VL 解释可见影响和重建建议。",
            "navigate_to": "/disaster-assess",
            "navigate_query": {"auto_assess": "1"},
            "action": {"type": "acquire_assessment_imagery", "event_id": context.get("event_id") or "dixie_fire_2021"},
            "source_mode": "structured",
        }}
    if needs_imagery:
        phase = "comparison_pre" if "灾前" in message else "comparison_post" if "灾后" in message else "primary"
        return {"ok": True, "data": {
            "message": "正在检查本地影像目录并检索相应时段的卫星场景；下载和波段检查结果将返回在对话中。",
            "action": {"type": "acquire_imagery", "event_id": "dixie_fire_2021" if "Dixie" in message or "迪克西" in message else context.get("event_id") or "dixie_fire_2021", "phase": phase},
            "source_mode": "structured",
        }}
    # Local UI actions only. No external model or data service is called here.
    if any(word in message for word in ("实时火点", "全球火点", "全局影像", "全球影像")):
        return {"ok": True, "data": {
            "message": "已打开实时监测并缩小到全球视角。当前已接入的热异常仍以所选支持区域为准；全局底图不代表全球火点均已下载。",
            "navigate_to": "/realtime-monitor",
            "navigate_query": {"mode": "realtime", "focus": "global"},
            "source_mode": "structured",
        }}
    if "加州" in message and any(word in message for word in ("火", "聚焦", "数据")):
        return {"ok": True, "data": {
            "message": "已聚焦加州。核查火情需要卫星影像与热异常、逐时风速风向/温湿度/降水、DEM、植被燃料、道路和水源。请以监测页数据目录的可用状态为准，缺失项不能当作已获取。",
            "navigate_to": "/realtime-monitor",
            "navigate_query": {"mode": "realtime", "focus": "california"},
            "source_mode": "structured",
        }}
    if any(word in message for word in ("推演", "推理", "蔓延", "预测")) and any(word in message for word in ("火", "风", "气象", "开始", "打开", "看看")):
        horizon = _requested_horizon(message)
        if horizon is None and any(phrase in message for phrase in ('开始推演', '运行推演', '推演火情', '帮我预测', '开始预测')):
            horizon = 240
        interval = "120" if any(word in message for word in ("两小时", "2小时", "2 小时")) else "60" if any(word in message for word in ("每小时", "1小时", "1 小时")) else None
        return {"ok": True, "data": {
            "message": (f"已准备推演 {horizon // 60} 小时后的火势。将使用当前推演页气象输入提交模型，结果显示在右侧推演输出卡片和地图时间轴。" if horizon else "已打开火情推演。可设置预测总时长与气象条件，再运行模型。"),
            "navigate_to": "/command-center",
            "navigate_query": {**({"weather_interval": interval} if interval else {}), **({"forecast_hours": str(horizon // 60)} if horizon else {}), **{key: str(value) for key, value in weather.items()}},
            "action": {"type": "run_spread", "horizon_minutes": horizon, **weather} if horizon else None,
            "source_mode": "structured",
        }}
    if any(word in message for word in ("路线", "路径", "资源调度", "消防队伍", "受灾点", "救火人员", "水资源", "食物")):
        return {"ok": True, "data": {
            "message": "正在读取当前推演火线、生成推荐目标并计算消防队演练路径；真实道路与队伍位置仍需补充。",
            "navigate_to": "/planning",
            "navigate_query": {"auto_plan": "1"},
            "source_mode": "structured",
        }}
    if any(word in message for word in ("核验", "候选火点", "目标识别", "千问视觉")):
        return {"ok": True, "data": {
            "message": "正在打开当前候选点并调用影像预处理、目标识别和 Qwen-VL 复核；缺少同期影像时会显示具体阻塞原因。",
            "navigate_to": "/visual-verification",
            "navigate_query": {"mode": "qwen", "auto_review": "1"},
            "source_mode": "structured",
        }}
    if any(word in message for word in ("灾前灾后", "灾后评估", "重建建议")):
        return {"ok": True, "data": {
            "message": "正在检查灾前灾后影像目录；两期多波段影像就绪后将执行真实变化检测和千问视觉评估。",
            "navigate_to": "/disaster-assess",
            "navigate_query": {"auto_assess": "1"},
            "action": {"type": "acquire_assessment_imagery", "event_id": context.get("event_id") or "dixie_fire_2021"},
            "source_mode": "structured",
        }}
    destination = next(
        (path for label, path in PAGES.items()
         if label in message and any(verb in message for verb in ("打开", "前往", "进入", "切换到"))),
        None,
    )
    if destination:
        return {"ok": True, "data": {
            "message": "已切换到对应工作页。请在页面中核对真实数据与状态。",
            "navigate_to": destination, "source_mode": "structured",
        }}

    event_name = context.get("event_name") or context.get("event_id") or "未选择事件"
    status = context.get("workflow_status") or "尚未运行"
    stage = context.get("current_stage") or "未知"
    if any(word in message for word in ("状态", "进度", "事件", "火情")):
        answer = f"当前事件：{event_name}；工作流状态：{status}；当前阶段：{stage}。"
        if context.get("confirmed"):
            answer += " 候选火点已有人工确认记录。"
        else:
            answer += " 尚无人工确认记录。"
    elif any(word in message for word in ("路线", "路径", "资源")):
        answer = (
            f"当前路线方案：{'已生成' if context.get('route_plan_id') else '未生成'}；"
            f"资源方案：{'已生成' if context.get('resource_plan_id') else '未生成'}。"
            "请到规划页核对路线和分配依据。"
        )
    elif any(word in message for word in ("推演", "蔓延")):
        answer = (
            f"当前火势推演：{'已生成' if context.get('spread_run_id') else '未生成'}。"
            "请到推演页查看计算输入和结果。"
        )
    else:
        answer = "本地对话可报告当前事件状态，或按“打开监测/核验/推演/规划/评估”切换页面。复杂分析请在对应工作页运行。"
    return {"ok": True, "data": {"message": answer, "source_mode": "structured"}}
