from __future__ import annotations

from typing import Any


STAGE_ORDER = [
    "data_preparation",
    "fire_verification",
    "situation",
    "spread",
    "spatial_risk",
    "scenario",
    "resource_dispatch",
    "route_planning",
    "commander",
]

STAGE_LABELS = {
    "data_preparation": "数据准备",
    "fire_verification": "火点核验",
    "situation": "态势评估",
    "spread": "火势推演",
    "spatial_risk": "空间风险",
    "scenario": "应急场景",
    "resource_dispatch": "资源调度",
    "route_planning": "路径规划",
    "commander": "指挥决策",
}

STAGE_PAGES = {
    "data_preparation": "/realtime-monitor",
    "fire_verification": "/visual-verification",
    "situation": "/command-center",
    "spread": "/command-center",
    "spatial_risk": "/command-center",
    "scenario": "/planning",
    "resource_dispatch": "/planning",
    "route_planning": "/planning",
    "commander": "/planning",
}


def _choice(
    choice_id: str,
    label: str,
    description: str,
    *,
    kind: str = "secondary",
    navigate_to: str | None = None,
    navigate_query: dict[str, str] | None = None,
    action: dict[str, Any] | None = None,
    prompt: str | None = None,
) -> dict[str, Any]:
    return {
        "id": choice_id,
        "label": label,
        "description": description,
        "kind": kind,
        "navigate_to": navigate_to,
        "navigate_query": navigate_query or {},
        "action": action,
        "prompt": prompt,
    }


def _completed_steps(context: dict[str, Any]) -> list[str]:
    stages = context.get("stages") or []
    completed = [str(item.get("stage")) for item in stages if item.get("status") == "COMPLETED"]
    if completed:
        return completed
    current = str(context.get("current_stage") or "")
    if current in STAGE_ORDER:
        return STAGE_ORDER[: STAGE_ORDER.index(current)]
    return []


def _progress(context: dict[str, Any]) -> int:
    if str(context.get("workflow_status") or "").upper() == "COMPLETED":
        return 88
    current = str(context.get("current_stage") or "")
    if current not in STAGE_ORDER:
        return 6
    stage = next(
        (item for item in (context.get("stages") or []) if item.get("stage") == current),
        {},
    )
    stage_progress = max(0, min(100, int(stage.get("progress") or 0)))
    return min(86, round((STAGE_ORDER.index(current) + stage_progress / 100) / len(STAGE_ORDER) * 86))


def _proposal_guidance(context: dict[str, Any], event_id: str) -> dict[str, Any] | None:
    proposal = context.get("last_agent_result")
    if not isinstance(proposal, dict):
        return None
    action = proposal.get("action") if isinstance(proposal.get("action"), dict) else None
    navigate_to = proposal.get("navigate_to")
    navigate_query = proposal.get("navigate_query") if isinstance(proposal.get("navigate_query"), dict) else {}
    choices: list[dict[str, Any]] = []
    title = "继续处理本次问题"
    message = str(proposal.get("message") or "请选择是否执行智能体根据本次问题建议的下一步。")

    if action:
        action_type = str(action.get("type") or "")
        labels = {
            "start_workflow": ("启动建议的工作流", "执行数据准备并推进到下一个人工决策门"),
            "acquire_imagery": ("检查并获取同期影像", "执行影像目录检查、五波段校验和官方来源检索"),
            "acquire_assessment_imagery": ("获取灾前灾后影像", "为变化检测准备两期真实影像"),
            "run_spread": ("运行建议的火势推演", "使用本次问题中的时长与气象参数提交模型"),
            "generate_report": ("生成综合报告", "汇总当前已经确认的分析与决策记录"),
        }
        label, description = labels.get(action_type, ("执行建议操作", "执行智能体根据本次问题生成的受控操作"))
        choices.append(_choice(
            f"confirm_{action_type or 'action'}",
            label,
            description,
            kind="primary",
            action={**action, "event_id": action.get("event_id") or event_id},
            navigate_to=str(navigate_to) if navigate_to else None,
            navigate_query={str(key): str(value) for key, value in navigate_query.items()},
        ))
        title = "请确认是否执行"

    elif navigate_to:
        choices.append(_choice(
            "open_agent_result",
            "查看本次查询结果",
            "按智能体返回的地点和范围打开对应工作页",
            kind="primary",
            navigate_to=str(navigate_to),
            navigate_query={str(key): str(value) for key, value in navigate_query.items()},
        ))
        title = "查询结果已经准备好"

    if proposal.get("source_mode") == "tool_agent":
        choices.append(_choice(
            "explain_tool_evidence",
            "解释数据证据与缺口",
            "说明本次真实工具查询使用了哪些来源、还缺少什么",
            prompt="请结合刚才的工具查询结果，说明数据来源、时间范围、可信边界和下一步数据缺口",
        ))

    if not choices:
        return None
    return {
        "phase": "pre_fire",
        "phase_label": "本次问题",
        "title": title,
        "message": message,
        "progress": 8,
        "current_stage": "request_review",
        "current_stage_label": "等待确认",
        "waiting_for": "user_action_confirmation",
        "completed_steps": [],
        "choices": choices,
    }


def build_next_steps(page: str, context: dict[str, Any]) -> dict[str, Any]:
    event_id = str(context.get("event_id") or "dixie_fire_2021")
    event_name = str(context.get("event_name") or event_id)
    user_message = str(context.get("last_user_message") or "").strip()
    workflow_run_id = str(context.get("workflow_run_id") or "")
    status = str(context.get("workflow_status") or "").upper()
    current_stage = str(context.get("current_stage") or "data_preparation")
    completed = _completed_steps(context)

    if not user_message:
        return {
            "phase": "idle",
            "phase_label": "等待任务",
            "title": "你想了解哪一处火情？",
            "message": "请描述地点、时间和目标。我会在理解问题后再给出相关操作，不会预先启动流程。",
            "progress": 0,
            "current_stage": "idle",
            "current_stage_label": "尚未提问",
            "waiting_for": "user_request",
            "completed_steps": [],
            "choices": [],
        }

    # A persisted workflow owns the next step once it has started. A fresh
    # chat may use the last assistant result to propose an action, but it must
    # never hide a real human decision gate such as fire verification.
    if not workflow_run_id or status in {"", "尚未运行", "UNAVAILABLE"}:
        proposal_guidance = _proposal_guidance(context, event_id)
        if proposal_guidance is not None:
            return proposal_guidance

    if not workflow_run_id or status in {"", "尚未运行", "UNAVAILABLE"}:
        realtime = any(word in user_message for word in ("实时", "当前火点", "现在", "FIRMS", "热异常"))
        verification = any(word in user_message for word in ("核验", "候选火点", "目标检测", "影像", "遥感"))
        spread = any(word in user_message for word in ("推演", "预测", "蔓延", "火势"))
        planning = any(word in user_message for word in ("规划", "路线", "调度", "资源", "救援"))
        assessment = any(word in user_message for word in ("灾后", "评估", "受灾", "重建", "灾前灾后"))
        report = "报告" in user_message
        complete = any(word in user_message for word in ("完整", "全流程", "整个流程", "从灾前", "灾前灾中灾后"))

        if realtime:
            choices = [
                _choice("open_requested_monitor", "查看相关实时火点", "打开本次问题对应的监测视角和 FIRMS 候选点", kind="primary", navigate_to="/realtime-monitor"),
                _choice("explain_hotspot_evidence", "说明火点数据依据", "继续查询候选点时间、来源和可用性", prompt=f"请说明“{user_message}”对应候选火点的数据时间、来源和限制"),
            ]
            title = "继续查看本次实时火情"
            message = "已根据你的问题定位到实时监测任务。下面只显示与实时火点有关的操作。"
        elif verification:
            choices = [
                _choice("open_requested_verification", "进入火点核验", "在 Cesium 中选择候选点并运行影像检测", kind="primary", navigate_to="/visual-verification"),
                _choice("acquire_requested_imagery", "检查同期影像", "检查本次事件的五波段影像是否齐全", action={"type": "acquire_imagery", "event_id": event_id, "phase": "primary"}),
            ]
            title = "继续完成火点核验"
            message = "已识别为候选火点或遥感影像核验任务。"
        elif assessment:
            choices = [
                _choice("open_requested_assessment", "进入灾后评估", "查看灾前灾后影像和变化检测", kind="primary", navigate_to="/disaster-assess"),
                _choice("acquire_requested_comparison", "获取对比影像", "检查灾前和灾后五波段影像", action={"type": "acquire_assessment_imagery", "event_id": event_id}),
            ]
            title = "继续开展灾后评估"
            message = "已识别为灾后影响或重建分析任务。"
        elif spread:
            choices = [
                _choice("start_spread_workflow", "准备并运行火势推演", "先完成数据和火点确认，再自动推进到推演", kind="primary", action={"type": "start_workflow", "event_id": event_id, "horizon_minutes": 240}),
                _choice("open_spread_page", "查看推演条件", "核对气象、时长和已有火线结果", navigate_to="/command-center"),
            ]
            title = "继续准备火势推演"
            message = "已识别为火势预测任务。真实推演前仍需满足数据和人工确认条件。"
        elif planning:
            choices = [
                _choice("start_planning_workflow", "准备完整规划依据", "运行核验、推演和风险分析后进入规划", kind="primary", action={"type": "start_workflow", "event_id": event_id, "horizon_minutes": 240}),
                _choice("open_planning_page", "查看现有规划", "查看当前已有的目标、资源和演练路线", navigate_to="/planning"),
            ]
            title = "继续准备应急规划"
            message = "已识别为资源、路线或救援规划任务。"
        elif report:
            choices = [
                _choice("start_report_workflow", "先生成分析依据", "完成核验、推演、规划和人工决策后才能生成报告", kind="primary", action={"type": "start_workflow", "event_id": event_id, "horizon_minutes": 240}),
            ]
            title = "报告需要完整分析结果"
            message = "当前还没有可用于报告的完整决策链，需先运行并确认上游阶段。"
        elif complete:
            choices = [
                _choice("start_requested_workflow", "启动本次完整工作流", "按你的问题依次执行核验、推演、规划、评估和报告准备", kind="primary", action={"type": "start_workflow", "event_id": event_id, "horizon_minutes": 240, "acquire_imagery": True}, navigate_to="/visual-verification"),
            ]
            title = "开始本次完整分析"
            message = f"已将你的问题关联到 {event_name}，工作流会在真实人工决策门暂停。"
        else:
            choices = []
            title = "已理解本次问题"
            message = "回答已显示在下方。需要执行监测、核验、推演或规划时，我会再提供与问题对应的操作。"

        return {
            "phase": "pre_fire",
            "phase_label": "问题研判",
            "title": title,
            "message": message,
            "progress": 6,
            "current_stage": "data_preparation",
            "current_stage_label": "尚未启动",
            "waiting_for": "workflow_start",
            "completed_steps": [],
            "choices": choices,
        }

    if status == "FAILED":
        page_target = STAGE_PAGES.get(current_stage, page or "/realtime-monitor")
        return {
            "phase": "during_fire",
            "phase_label": "流程异常",
            "title": f"{STAGE_LABELS.get(current_stage, current_stage)}未完成",
            "message": str(context.get("workflow_error") or "当前阶段执行失败，请检查阶段错误或重新启动流程。"),
            "progress": _progress(context),
            "current_stage": current_stage,
            "current_stage_label": STAGE_LABELS.get(current_stage, current_stage),
            "waiting_for": "error_resolution",
            "completed_steps": completed,
            "choices": [
                _choice("inspect_failure", "查看问题阶段", "打开对应工作页核对输入和错误信息", kind="primary", navigate_to=page_target),
                _choice("restart_workflow", "重新启动工作流", "保留事件数据并创建新的流程运行", action={"type": "start_workflow", "event_id": event_id, "horizon_minutes": 240}),
            ],
        }

    if status == "WAITING_FOR_INPUT" and current_stage == "fire_verification":
        workflow_metadata = context.get("workflow_metadata") or {}
        verification_stage = str(
            workflow_metadata.get("verification_substage")
            or context.get("verification_substage")
            or "imagery_selection"
        )
        stage_copy = {
            "imagery_selection": (
                "先选择火灾地点同期影像",
                "选择影像后，系统会按影像获取时间和覆盖范围查询 FIRMS 热异常候选点。",
            ),
            "firms_candidates": (
                "选择 FIRMS 候选火点",
                "候选点只是热异常观测，请选择一个候选点并运行局部影像目标检测。",
            ),
            "target_detection": (
                "继续进行 Qwen-VL 综合复核",
                "YOLO 结果已经保留，可结合真实影像与检测证据运行千问视觉复核。",
            ),
            "qwen_review": (
                "等待人工确认火点",
                "FIRMS、YOLO 和 Qwen-VL 证据已经汇总，请由操作人员确认、排除或要求补充影像。",
            ),
            "human_confirmation": (
                "等待人工确认火点",
                "检测证据已经准备完成，人工确认后才允许进入火势推演。",
            ),
        }
        verification_title, verification_message = stage_copy.get(
            verification_stage,
            stage_copy["imagery_selection"],
        )
        return {
            "phase": "during_fire",
            "phase_label": "灾中研判",
            "title": verification_title,
            "message": verification_message,
            "progress": max(20, _progress(context)),
            "current_stage": current_stage,
            "current_stage_label": STAGE_LABELS[current_stage],
            "waiting_for": "human_fire_confirmation",
            "completed_steps": completed,
            "choices": [
                _choice("open_verification", "继续影像核验", "依次完成影像选择、FIRMS 候选、YOLO、Qwen-VL 与人工确认", kind="primary", navigate_to="/visual-verification"),
                _choice("acquire_imagery", "补充同期影像", "由数据智能体检查目录并检索缺少的五波段影像", action={"type": "acquire_imagery", "event_id": event_id, "phase": "primary"}),
            ],
        }

    if status == "WAITING_FOR_INPUT" and current_stage == "situation" and context.get("confirmation_id"):
        return {
            "phase": "during_fire",
            "phase_label": "火势推演",
            "title": "可信火点已确认，请配置首次推演",
            "message": "智能体会读取当前事件可用的气象数据数量和记录间隔。请在右侧填写推理时长与气象更新间隔；保存后仍需在推理页面手动点击开始。",
            "progress": max(36, _progress(context)),
            "current_stage": current_stage,
            "current_stage_label": "推演参数确认",
            "waiting_for": "spread_configuration",
            "completed_steps": completed,
            "choices": [
                _choice("configure_initial_spread", "前往推理页面", "在右侧智能体填写时长和更新间隔，再由用户手动启动推演", kind="primary", navigate_to="/command-center"),
            ],
        }

    if status == "WAITING_FOR_INPUT" and current_stage == "scenario":
        return {
            "phase": "during_fire",
            "phase_label": "灾中处置",
            "title": "请选择应急场景方案",
            "message": "风险分析已经完成，系统生成了候选目标和资源方案。确认后才会继续资源与路线规划。",
            "progress": max(62, _progress(context)),
            "current_stage": current_stage,
            "current_stage_label": STAGE_LABELS[current_stage],
            "waiting_for": "human_scenario_confirmation",
            "completed_steps": completed,
            "choices": [
                _choice("review_scenario", "查看并调整方案", "在规划页核对目标点、队伍起点和资源需求", kind="primary", navigate_to="/planning"),
                _choice("confirm_scenario", "确认当前方案并继续", "明确采用当前候选方案，继续资源调度和路线计算", action={"type": "confirm_scenario"}),
            ],
        }

    if status == "WAITING_FOR_INPUT" and current_stage == "commander":
        return {
            "phase": "during_fire",
            "phase_label": "指挥复核",
            "title": "辅助决策等待人工审批",
            "message": "推演、风险、资源和路线结果已经汇总。请选择接受、退回修改或重新生成建议。",
            "progress": max(82, _progress(context)),
            "current_stage": current_stage,
            "current_stage_label": STAGE_LABELS[current_stage],
            "waiting_for": "commander_review",
            "completed_steps": completed,
            "choices": [
                _choice("review_decision", "查看决策详情", "在规划页核对依据、限制和演练路线", kind="primary", navigate_to="/planning"),
                _choice("approve_decision", "接受辅助决策", "记录人工确认，不代表下达真实救援命令", action={"type": "review_commander", "review_action": "approve"}),
                _choice("revise_decision", "退回场景调整", "返回场景配置重新选择目标与资源", action={"type": "review_commander", "review_action": "revise"}),
            ],
        }

    if status == "COMPLETED" and context.get("report_id"):
        return {
            "phase": "report",
            "phase_label": "报告完成",
            "title": "完整工作流程已闭环",
            "message": "灾中处置记录和综合报告已经生成。可以下载报告，或返回灾后评估继续补充影像结论。",
            "progress": 100,
            "current_stage": "report",
            "current_stage_label": "综合报告",
            "waiting_for": None,
            "completed_steps": completed or STAGE_ORDER,
            "choices": [
                _choice("open_assessment", "查看灾后评估", "检查变化检测、受灾范围和重建建议", kind="primary", navigate_to="/disaster-assess"),
                _choice("regenerate_report", "重新生成报告", "使用当前最新结果重新汇总综合报告", action={"type": "generate_report", "event_id": event_id}),
                _choice("start_new_analysis", "返回监测", "继续选择实时区域或新的历史事件", navigate_to="/realtime-monitor"),
            ],
        }

    if status == "COMPLETED":
        assessment_completed = bool(context.get("assessment_completed"))
        assessment = context.get("assessment") if isinstance(context.get("assessment"), dict) else {}
        if assessment_completed:
            area_hectares = assessment.get("area_hectares")
            area_text = f"，变化区域约 {float(area_hectares):.2f} 公顷" if area_hectares is not None else ""
            return {
                "phase": "post_fire",
                "phase_label": "灾后评估与报告",
                "title": "灾后影像分析已完成",
                "message": f"变化检测和 Qwen-VL 可见影响分析已经完成{area_text}。现在可以生成包含核验、火线、路线、资源、受灾范围、评估和重建建议的完整报告。",
                "progress": 96,
                "current_stage": "report_preparation",
                "current_stage_label": "完整报告",
                "waiting_for": "report_generation",
                "completed_steps": completed or STAGE_ORDER,
                "choices": [
                    _choice("generate_report", "生成完整综合报告", "汇总全流程真实结果、来源、限制和人工决策记录", kind="primary", action={"type": "generate_report", "event_id": event_id}),
                    _choice("review_assessment", "复核灾后评估", "查看受灾范围、千问解释和重建建议", navigate_to="/disaster-assess"),
                ],
            }
        return {
            "phase": "post_fire",
            "phase_label": "灾后评估与报告",
            "title": "应急工作流已完成",
            "message": "现在可以开展灾前灾后影像评估，或基于已确认的决策记录生成可下载报告。",
            "progress": 88,
            "current_stage": "post_fire_assessment",
            "current_stage_label": "灾后评估",
            "waiting_for": "post_fire_choice",
            "completed_steps": completed or STAGE_ORDER,
            "choices": [
                _choice("start_assessment", "开展灾后评估", "获取灾前灾后影像并计算可见变化", kind="primary", navigate_to="/disaster-assess", navigate_query={"auto_assess": "1"}, action={"type": "acquire_assessment_imagery", "event_id": event_id}),
                _choice("inspect_planning", "复核处置结果", "查看资源方案、路线和指挥决策记录", navigate_to="/planning"),
            ],
        }

    label = STAGE_LABELS.get(current_stage, current_stage)
    target = STAGE_PAGES.get(current_stage, page or "/realtime-monitor")
    return {
        "phase": "during_fire",
        "phase_label": "自动执行中",
        "title": f"正在执行：{label}",
        "message": "工作流会自动推进到下一个真实人工决策门；无需逐项输入命令。",
        "progress": _progress(context),
        "current_stage": current_stage,
        "current_stage_label": label,
        "waiting_for": None,
        "completed_steps": completed,
        "choices": [
            _choice("open_current_stage", "查看当前阶段", "打开对应工作页查看输入、运行状态和结果", kind="primary", navigate_to=target),
            _choice("ask_status", "说明当前进度", "让智能体解释当前阶段和后续步骤", prompt="说明当前工作流进度、数据依据和下一步"),
        ],
    }
