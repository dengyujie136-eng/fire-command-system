from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import desc, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.commander_agent import CommanderAgent
from app.agents.context import AgentAnalysisContext
from app.agents.resource_agent import ResourceAgent, ResourceAgentTask
from app.agents.route_agent import RouteAgent, RouteTask
from app.agents.situation_agent import SituationAgent
from app.db.session import AsyncSessionLocal
from app.integrations.schemas import CandidateContext, CapabilityStatus, EventContext, IncidentContext
from app.integrations.spatial_risk import SpatialRiskAdapter
from app.integrations.spread import SpreadAdapter
from app.integrations.trusted_ignition import TrustedIgnitionAdapter
from app.models.decision import AgentPacket, DecisionRun
from app.models.event import FireEvent
from app.models.recommendation import RecommendationPackage
from app.models.spatial_analysis import SpatialAnalysisRun
from app.models.spread import FireFrontStep, SimulationRun
from app.models.workflow import (
    EmergencyScenario,
    ScenarioLocation,
    ScenarioResource,
    ScenarioResourcePlan,
    ScenarioRoutePlan,
    WorkflowRun,
    WorkflowStageRun,
)
from app.schemas.workflow import (
    CommanderReviewRequest,
    HumanVerificationRequest,
    ScenarioConfirmRequest,
    ScenarioGenerateRequest,
    WorkflowCreateRequest,
    WorkflowSpreadRerunRequest,
)
from app.services.resources import ResourceRequirement, ResourceTask
from app.services.scenario_recommendation_service import (
    RULE_VERSION,
    ScenarioRecommendationService,
    ScenarioRoadNetworkProvider,
    resources_from_blueprint,
)
from app.services.spread_service import build_feature_collection
from app.visual_verification.candidate_service import ingest_candidate_envelope
from app.visual_verification.models import FireConfirmationRecord, ImageryAssetCatalogRecord, VisualVerificationCaseRecord
from app.visual_verification.schemas import HotspotCandidateEnvelope


STAGES = (
    "data_preparation",
    "fire_verification",
    "situation",
    "spread",
    "spatial_risk",
    "scenario",
    "resource_dispatch",
    "route_planning",
    "commander",
)
TERMINAL_STATUSES = {"COMPLETED", "FAILED", "UNAVAILABLE", "SKIPPED"}


def _now() -> datetime:
    return datetime.now(UTC)


async def _run_or_404(db: AsyncSession, workflow_run_id: str) -> WorkflowRun:
    run = await db.scalar(select(WorkflowRun).where(WorkflowRun.workflow_run_id == workflow_run_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return run


async def _stage(db: AsyncSession, workflow_run_id: str, stage: str) -> WorkflowStageRun:
    item = await db.scalar(
        select(WorkflowStageRun).where(
            WorkflowStageRun.workflow_run_id == workflow_run_id,
            WorkflowStageRun.stage == stage,
        )
    )
    if item is None:
        raise RuntimeError(f"Workflow stage not found: {stage}")
    return item


async def _set_stage(
    db: AsyncSession,
    run: WorkflowRun,
    stage_name: str,
    status: str,
    *,
    progress: int,
    message: str,
    result_id: str | None = None,
    error: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> WorkflowStageRun:
    item = await _stage(db, run.workflow_run_id, stage_name)
    item.status = status
    item.progress = max(0, min(100, progress))
    item.message = message
    item.result_id = result_id
    item.error = error
    if metadata is not None:
        item.metadata_json = metadata
    if status == "RUNNING":
        item.started_at = _now()
        item.finished_at = None
    elif status in {"PENDING", "READY"}:
        item.started_at = None
        item.finished_at = None
    if status in TERMINAL_STATUSES or status == "WAITING_FOR_INPUT":
        item.finished_at = _now() if status in TERMINAL_STATUSES else None
    run.current_stage = stage_name
    await db.flush()
    return item


def _spread_stage_metadata(
    spread: Any,
    weather: list[Any],
    *,
    parameter_source: str = "member_a_hourly_weather",
    parameter_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run = spread.run
    result_summary = dict(run.result_summary or {})
    input_snapshot = dict(run.input_snapshot or {})
    timeline = [frame.model_dump(mode="json") for frame in weather]
    return {
        "engine": run.engine,
        "final_area_km2": run.final_area_km2,
        "max_radius_km": run.max_radius_km,
        "direction_deg": run.spread_direction_deg,
        "step_count": len(spread.steps),
        "fallback_used": run.fallback_used,
        "environment": timeline[0] if timeline else {},
        "environment_timeline": timeline,
        "weather_source": timeline[0].get("source") if timeline else None,
        "parameter_source": parameter_source,
        "parameter_overrides": parameter_overrides or {},
        "input_source": input_snapshot.get("input_source"),
        "landscape": result_summary.get("landscape")
        or input_snapshot.get("landscape")
        or {},
        "model": result_summary.get("model") or {},
    }


async def _invalidate_downstream_results(
    db: AsyncSession,
    run: WorkflowRun,
    *,
    previous_spread_run_id: str | None,
) -> None:
    previous = {
        "spread_run_id": previous_spread_run_id,
        "spatial_analysis_id": run.spatial_analysis_id,
        "scenario_id": run.scenario_id,
        "resource_plan_id": run.resource_plan_id,
        "route_plan_id": run.route_plan_id,
        "decision_run_id": run.decision_run_id,
        "recommendation_id": run.recommendation_id,
    }
    run.spatial_analysis_id = None
    run.scenario_id = None
    run.resource_plan_id = None
    run.route_plan_id = None
    run.decision_run_id = None
    run.recommendation_id = None
    run.metadata_json = {
        **dict(run.metadata_json or {}),
        "last_invalidated_results": previous,
        "last_invalidated_at": _now().isoformat(),
    }
    await _set_stage(
        db,
        run,
        "situation",
        "PENDING",
        progress=0,
        message="等待重新推演后的环境态势汇总。",
        metadata={"invalidated": True, "reason": "spread_parameters_changed"},
    )
    await _set_stage(
        db,
        run,
        "spatial_risk",
        "PENDING",
        progress=0,
        message="等待新的火线结果重新计算空间风险。",
        metadata={"invalidated": True, "reason": "spread_parameters_changed"},
    )
    await _set_stage(
        db,
        run,
        "scenario",
        "PENDING",
        progress=0,
        message="原应急场景已失效，等待新的风险结果生成候选。",
        metadata={"invalidated": True, "reason": "spread_parameters_changed"},
    )
    await _set_stage(
        db,
        run,
        "resource_dispatch",
        "PENDING",
        progress=0,
        message="原资源调度已失效，等待新场景人工确认。",
        metadata={"invalidated": True, "reason": "spread_parameters_changed"},
    )
    await _set_stage(
        db,
        run,
        "route_planning",
        "PENDING",
        progress=0,
        message="原可达性路径已失效，等待新场景人工确认。",
        metadata={"invalidated": True, "reason": "spread_parameters_changed"},
    )
    await _set_stage(
        db,
        run,
        "commander",
        "PENDING",
        progress=0,
        message="原辅助决策已失效，等待新路径和资源结果。",
        metadata={"invalidated": True, "reason": "spread_parameters_changed"},
    )


async def list_events(db: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        await db.execute(select(FireEvent).order_by(desc(FireEvent.started_at), FireEvent.name))
    ).scalars().all()
    return [
        {
            "event_id": row.event_id,
            "name": row.name,
            "status": row.status,
            "mode": "historical" if row.source_mode == "historical" else row.source_mode,
            "source_mode": row.source_mode,
            "started_at": row.started_at,
            "center": [row.ignition_longitude, row.ignition_latitude],
        }
        for row in rows
    ]


async def data_readiness(db: AsyncSession, event_id: str) -> dict[str, Any]:
    names: list[str] = []
    try:
        rows = await db.execute(
            text("SELECT name, local_path FROM fire_data_manifests WHERE event_id = :event_id"),
            {"event_id": event_id},
        )
        names = [f"{row.name} {row.local_path}".lower() for row in rows]
    except Exception:
        await db.rollback()
    joined = " ".join(names)
    catalog_rows = (await db.execute(select(ImageryAssetCatalogRecord).where(
        ImageryAssetCatalogRecord.event_id == event_id,
        ImageryAssetCatalogRecord.quality_status == "available",
    ))).scalars().all()
    real_scenes: dict[str, set[str]] = {}
    for asset in catalog_rows:
        metadata = asset.metadata_json or {}
        path = metadata.get("local_path")
        if asset.is_simulated or not path or not Path(path).is_file():
            continue
        scene = metadata.get("scene_id") or asset.asset_id
        real_scenes.setdefault(scene, set()).update(asset.bands or [])
    sentinel_ready = any({"B02", "B03", "B04", "B08", "B12"} <= bands for bands in real_scenes.values())
    definitions = [
        ("FIRMS", ("firms",), "Hotspot observations"),
        ("Weather", ("weather", "nasa power"), "Hourly/daily weather"),
        ("MTBS", ("mtbs", "burned"), "Observed burned area"),
        ("DEM", ("dem", "copernicus"), "Terrain and slope"),
        ("Fuel", ("fuel", "worldcover"), "Fuel and land cover"),
        ("Sentinel", ("sentinel",), "Before/after optical imagery"),
        ("GOES", ("goes",), "Geostationary imagery demo"),
    ]
    items = []
    for label, tokens, description in definitions:
        available = any(token in joined for token in tokens)
        if label == "Sentinel":
            available = sentinel_ready
        if label == "GOES":
            available = available or any("goes" in (row.source_name or "").lower() for row in catalog_rows)
        items.append({"name": label, "status": "Available" if available else "Missing", "description": description})
    return {
        "event_id": event_id,
        "items": items,
        "available": sum(1 for item in items if item["status"] == "Available"),
        "total": len(items),
        "sentinel": "Available" if sentinel_ready else "Missing",
    }


async def create_workflow(db: AsyncSession, event_id: str, request: WorkflowCreateRequest) -> WorkflowRun:
    event = await db.scalar(select(FireEvent).where(FireEvent.event_id == event_id))
    if event is None:
        raise HTTPException(status_code=404, detail="Fire event not found")
    run = WorkflowRun(
        workflow_run_id=f"wfr_{uuid4().hex[:18]}",
        event_id=event_id,
        mode=request.mode,
        status="RUNNING",
        current_stage="data_preparation",
        candidate_id=request.candidate_id,
        confirmation_id=request.confirmation_id,
        horizon_minutes=request.horizon_minutes,
        threat_buffer_km=request.threat_buffer_km,
        started_at=_now(),
        metadata_json={"schema_version": "fire.workflow.v1", "event_name": event.name},
    )
    db.add(run)
    await db.flush()
    for index, stage_name in enumerate(STAGES):
        db.add(
            WorkflowStageRun(
                workflow_run_id=run.workflow_run_id,
                stage=stage_name,
                status="RUNNING" if index == 0 else "PENDING",
                progress=10 if index == 0 else 0,
                message="正在检查事件数据。" if index == 0 else "等待上游阶段。",
                started_at=_now() if index == 0 else None,
            )
        )
    await db.commit()
    await db.refresh(run)
    return run


async def _latest_case_and_confirmation(
    db: AsyncSession,
    run: WorkflowRun,
) -> tuple[VisualVerificationCaseRecord | None, FireConfirmationRecord | None]:
    confirmation = None
    case = None
    if run.confirmation_id:
        confirmation = await db.scalar(
            select(FireConfirmationRecord).where(FireConfirmationRecord.confirmation_id == run.confirmation_id)
        )
        if confirmation:
            case = await db.scalar(
                select(VisualVerificationCaseRecord).where(
                    VisualVerificationCaseRecord.visual_case_id == confirmation.visual_case_id
                )
            )
    if case is None:
        statement = select(VisualVerificationCaseRecord).where(VisualVerificationCaseRecord.event_id == run.event_id)
        if run.candidate_id:
            statement = statement.where(VisualVerificationCaseRecord.source_candidate_id == run.candidate_id)
        case = await db.scalar(statement.order_by(desc(VisualVerificationCaseRecord.observed_at)).limit(1))
    if case and confirmation is None:
        confirmation = await db.scalar(
            select(FireConfirmationRecord)
            .where(
                FireConfirmationRecord.visual_case_id == case.visual_case_id,
                FireConfirmationRecord.is_current.is_(True),
                FireConfirmationRecord.status == "confirmed",
            )
            .order_by(desc(FireConfirmationRecord.version))
            .limit(1)
        )
    return case, confirmation


async def _auto_import_candidate(db: AsyncSession, event: FireEvent) -> VisualVerificationCaseRecord | None:
    try:
        row = (
            await db.execute(
                text(
                    """
                    SELECT candidate_id, observed_at, ST_X(location_geom) AS longitude,
                           ST_Y(location_geom) AS latitude, confidence_score AS confidence, frp_mw
                    FROM fire_hotspots WHERE event_id = :event_id
                    ORDER BY observed_at LIMIT 1
                    """
                ),
                {"event_id": event.event_id},
            )
        ).mappings().first()
    except Exception:
        await db.rollback()
        return None
    if not row:
        return None
    observed_at = row["observed_at"]
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)
    payload = HotspotCandidateEnvelope.model_validate(
        {
            "schema_version": "fire.hotspot.candidate.v0.1",
            "event_id": event.event_id,
            "generated_at": _now(),
            "candidates": [
                {
                    "candidate_id": row["candidate_id"],
                    "event_id": event.event_id,
                    "event_name": event.name,
                    "location": {"longitude": row["longitude"], "latitude": row["latitude"], "crs": "EPSG:4326"},
                    "observed_at": observed_at,
                    "cluster_point_count": 1,
                    "cluster_mean_confidence": row["confidence"],
                    "cluster_max_frp_mw": row["frp_mw"],
                    "status": "candidate",
                    "data_owner": {
                        "organization": "NASA FIRMS archive",
                        "source_product": "FIRMS_ARCHIVE_DB",
                        "license": "NASA FIRMS attribution required",
                        "attribution_required": True,
                    },
                    "imagery_status": "unavailable",
                    "imagery_refs": [],
                    "is_simulated": False,
                    "replay": {"is_replay": True, "replay_interval_minutes": 10, "replay_source": "historical_hotspot_database"},
                    "product_fields": {"auto_imported_by": "workflow_runtime_v1"},
                }
            ],
        }
    )
    result = await ingest_candidate_envelope(db, payload)
    if not result.items:
        return None
    return await db.scalar(
        select(VisualVerificationCaseRecord).where(
            VisualVerificationCaseRecord.visual_case_id == result.items[0].case.visual_case_id
        )
    )


async def prepare_workflow(workflow_run_id: str) -> None:
    async with AsyncSessionLocal() as db:
        run = await _run_or_404(db, workflow_run_id)
        try:
            readiness = await data_readiness(db, run.event_id)
            # Optional catalog probes may rollback their transaction. Reload the
            # run before reading ORM attributes so asyncpg never lazy-loads here.
            run = await _run_or_404(db, workflow_run_id)
            event = await db.scalar(select(FireEvent).where(FireEvent.event_id == run.event_id))
            case, confirmation = await _latest_case_and_confirmation(db, run)
            auto_imported = False
            if event is not None and (case is None or (event.source_mode == "historical" and case.is_simulated and not run.confirmation_id)):
                imported = await _auto_import_candidate(db, event)
                if imported is not None:
                    case = imported
                    confirmation = None
                    auto_imported = True
            if case:
                run.candidate_id = case.source_candidate_id
                run.visual_case_id = case.visual_case_id
            if confirmation:
                run.confirmation_id = confirmation.confirmation_id
            await _set_stage(
                db,
                run,
                "data_preparation",
                "COMPLETED",
                progress=100,
                message=f"数据目录已检查：{readiness['available']}/{readiness['total']} 类可用。",
                result_id=run.event_id,
                metadata={"readiness": readiness, "candidate_auto_imported": auto_imported},
            )
            run.status = "WAITING_FOR_INPUT"
            run.current_stage = "fire_verification"
            await _set_stage(
                db,
                run,
                "fire_verification",
                "WAITING_FOR_INPUT",
                progress=70 if confirmation else 30,
                message=("AI/演示核验结果已就绪，等待人工确认。" if confirmation else "候选点已接入，需在专业工作台准备影像并完成核验。"),
                result_id=confirmation.confirmation_id if confirmation else (case.visual_case_id if case else None),
                metadata={
                    "review_state": "AI_SUGGESTED" if confirmation else "UNCERTAIN",
                    "visual_status": case.status if case else "missing",
                    "imagery_status": case.imagery_status if case else "missing",
                    "confidence": confirmation.confidence if confirmation else None,
                },
            )
            await db.commit()
        except Exception as exc:
            await db.rollback()
            run = await _run_or_404(db, workflow_run_id)
            run.status = "FAILED"
            run.error = str(exc)
            await _set_stage(db, run, "data_preparation", "FAILED", progress=100, message="数据准备失败。", error=str(exc))
            await db.commit()


async def human_verify(db: AsyncSession, workflow_run_id: str, request: HumanVerificationRequest) -> WorkflowRun:
    run = await _run_or_404(db, workflow_run_id)
    case, confirmation = await _latest_case_and_confirmation(db, run)
    if request.action == "confirm":
        if request.confirmation_id:
            confirmation = await db.scalar(
                select(FireConfirmationRecord).where(FireConfirmationRecord.confirmation_id == request.confirmation_id)
            )
        if confirmation is None or confirmation.status != "confirmed":
            raise HTTPException(status_code=409, detail="A confirmed visual result is required before human confirmation")
        run.confirmation_id = confirmation.confirmation_id
        run.visual_case_id = confirmation.visual_case_id
        run.candidate_id = confirmation.source_candidate_id
        run.human_confirmation_state = "HUMAN_CONFIRMED"
        run.status = "RUNNING"
        await _set_stage(
            db, run, "fire_verification", "COMPLETED", progress=100,
            message="人工已确认可信火点。", result_id=confirmation.confirmation_id,
            metadata={"review_state": "HUMAN_CONFIRMED", "note": request.note, "confidence": confirmation.confidence},
        )
        await _set_stage(db, run, "situation", "READY", progress=0, message="可信火点已就绪，可开始态势评估。")
    elif request.action == "reject":
        run.human_confirmation_state = "HUMAN_REJECTED"
        run.status = "WAITING_FOR_INPUT"
        await _set_stage(
            db, run, "fire_verification", "COMPLETED", progress=100,
            message="人工已驳回当前候选点，请选择其他候选点。",
            metadata={"review_state": "HUMAN_REJECTED", "note": request.note},
        )
    else:
        run.human_confirmation_state = "UNCERTAIN"
        run.status = "WAITING_FOR_INPUT"
        await _set_stage(
            db, run, "fire_verification", "WAITING_FOR_INPUT", progress=75,
            message="需要进一步核验。", metadata={"review_state": "UNCERTAIN", "note": request.note},
        )
    await db.commit()
    await db.refresh(run)
    return run


async def execute_analysis(workflow_run_id: str) -> None:
    async with AsyncSessionLocal() as db:
        run = await _run_or_404(db, workflow_run_id)
        if run.human_confirmation_state != "HUMAN_CONFIRMED" or not run.confirmation_id:
            return
        try:
            event = await db.scalar(select(FireEvent).where(FireEvent.event_id == run.event_id))
            case = await db.scalar(
                select(VisualVerificationCaseRecord).where(VisualVerificationCaseRecord.visual_case_id == run.visual_case_id)
            )
            if event is None or case is None:
                raise RuntimeError("Workflow event or visual case is missing")
            await _set_stage(db, run, "situation", "RUNNING", progress=35, message="正在汇总可信火点和环境态势。")
            await db.commit()
            ignition = await TrustedIgnitionAdapter().resolve(db, event_id=run.event_id, confirmation_id=run.confirmation_id)
            await _set_stage(db, run, "spread", "RUNNING", progress=25, message="正在加载天气、DEM、Fuel 并执行栅格传播模型。")
            await db.commit()
            spread, weather = await SpreadAdapter().run(
                db, event_id=run.event_id, ignition=ignition, horizon_minutes=run.horizon_minutes
            )
            run.spread_run_id = spread.run.run_id
            await _set_stage(
                db, run, "spread", "COMPLETED", progress=100, message="火势推演已完成并保存 Fire Front。",
                result_id=spread.run.run_id,
                metadata=_spread_stage_metadata(spread, weather),
            )
            await _set_stage(db, run, "spatial_risk", "RUNNING", progress=35, message="正在执行风险网格和影响分析。")
            await db.commit()
            spatial = await SpatialRiskAdapter().run(
                db, event_id=run.event_id, spread_run_id=spread.run.run_id, threat_buffer_km=run.threat_buffer_km
            )
            run.spatial_analysis_id = spatial.run.analysis_id
            context = IncidentContext(
                event=EventContext(
                    event_id=event.event_id, name=event.name, status=event.status, scenario_id=event.scenario_id,
                    source_mode=event.source_mode, started_at=event.started_at,
                ),
                candidate=CandidateContext(
                    candidate_id=case.source_candidate_id, visual_case_id=case.visual_case_id,
                    observed_at=case.observed_at, longitude=case.longitude, latitude=case.latitude,
                    upstream_status=case.upstream_status, visual_status=case.status, imagery_status=case.imagery_status,
                    cluster_point_count=case.cluster_point_count, cluster_mean_confidence=case.cluster_mean_confidence,
                    cluster_max_frp_mw=case.cluster_max_frp_mw,
                ),
                ignition=ignition, visual_findings=[], weather=weather, spread=spread, spatial=spatial,
                resource=CapabilityStatus(status="unavailable", reason="scenario_not_confirmed", mode="synthetic"),
                route=CapabilityStatus(status="unavailable", reason="scenario_not_confirmed", mode="synthetic"),
            )
            situation_result = SituationAgent().run(context)
            await _set_stage(
                db, run, "situation", "COMPLETED", progress=100, message="SituationAgent 态势摘要已完成。",
                result_id=run.confirmation_id, metadata=situation_result["output"],
            )
            await _set_stage(
                db, run, "spatial_risk", "COMPLETED", progress=100, message="空间风险与影响分析已完成。",
                result_id=spatial.run.analysis_id,
                metadata={"summary": spatial.run.summary, "warnings": spatial.run.warnings, "is_simulated": spatial.run.is_simulated},
            )
            await db.commit()
            await generate_scenario(db, run.workflow_run_id, ScenarioGenerateRequest(mode="RECOMMENDED"))
        except Exception as exc:
            await db.rollback()
            run = await _run_or_404(db, workflow_run_id)
            current = run.current_stage if run.current_stage in {"situation", "spread", "spatial_risk"} else "situation"
            run.status = "FAILED"
            run.error = str(exc)
            await _set_stage(db, run, current, "FAILED", progress=100, message="工作流阶段失败，可重试。", error=str(exc))
            await db.commit()


async def request_spread_rerun(
    db: AsyncSession,
    workflow_run_id: str,
    request: WorkflowSpreadRerunRequest,
) -> WorkflowRun:
    run = await _run_or_404(db, workflow_run_id)
    if run.human_confirmation_state != "HUMAN_CONFIRMED" or not run.confirmation_id:
        raise HTTPException(
            status_code=409,
            detail="A human-confirmed fire point is required before a workflow spread rerun",
        )
    if not run.spread_run_id:
        raise HTTPException(
            status_code=409,
            detail="The initial workflow spread run must finish before it can be rerun",
        )
    spread_stage = await _stage(db, workflow_run_id, "spread")
    if spread_stage.status == "RUNNING":
        raise HTTPException(status_code=409, detail="A workflow spread calculation is already running")

    previous_spread_run_id = run.spread_run_id
    await _invalidate_downstream_results(
        db,
        run,
        previous_spread_run_id=previous_spread_run_id,
    )
    run.spread_run_id = None
    run.horizon_minutes = request.horizon_minutes
    run.status = "RUNNING"
    run.error = None
    await _set_stage(
        db,
        run,
        "spread",
        "RUNNING",
        progress=10,
        message="正在使用确认火点和指挥工作台环境参数重新执行真实火势推演。",
        metadata={
            "rerun": True,
            "previous_spread_run_id": previous_spread_run_id,
            "parameter_source": "command_center_manual_what_if",
            "parameter_overrides": request.model_dump(mode="json"),
        },
    )
    await db.commit()
    await db.refresh(run)
    return run


async def execute_spread_rerun(
    workflow_run_id: str,
    request: WorkflowSpreadRerunRequest,
) -> None:
    async with AsyncSessionLocal() as db:
        run = await _run_or_404(db, workflow_run_id)
        if run.human_confirmation_state != "HUMAN_CONFIRMED" or not run.confirmation_id:
            return
        try:
            event = await db.scalar(select(FireEvent).where(FireEvent.event_id == run.event_id))
            case = await db.scalar(
                select(VisualVerificationCaseRecord).where(
                    VisualVerificationCaseRecord.visual_case_id == run.visual_case_id
                )
            )
            if event is None or case is None:
                raise RuntimeError("Workflow event or visual case is missing")

            parameter_overrides = request.model_dump(mode="json")
            environment_overrides = {
                key: value
                for key, value in parameter_overrides.items()
                if key != "horizon_minutes"
            }
            environment_overrides["source"] = "command_center_parameter_adjustment"
            ignition = await TrustedIgnitionAdapter().resolve(
                db,
                event_id=run.event_id,
                confirmation_id=run.confirmation_id,
            )
            spread, weather = await SpreadAdapter().run(
                db,
                event_id=run.event_id,
                ignition=ignition,
                horizon_minutes=request.horizon_minutes,
                environment_overrides=environment_overrides,
                input_source=f"workflow_parameter_rerun:{run.workflow_run_id}",
                run_mode="what_if",
            )
            run.spread_run_id = spread.run.run_id
            run.metadata_json = {
                **dict(run.metadata_json or {}),
                "last_parameter_rerun": {
                    "spread_run_id": spread.run.run_id,
                    "parameters": parameter_overrides,
                    "completed_at": _now().isoformat(),
                },
            }
            await _set_stage(
                db,
                run,
                "spread",
                "COMPLETED",
                progress=100,
                message="重新推演已完成并保存新的真实 Fire Front。",
                result_id=spread.run.run_id,
                metadata=_spread_stage_metadata(
                    spread,
                    weather,
                    parameter_source="command_center_manual_what_if",
                    parameter_overrides=parameter_overrides,
                ),
            )
            await _set_stage(
                db,
                run,
                "spatial_risk",
                "RUNNING",
                progress=35,
                message="正在基于新的火线重新计算空间风险。",
            )
            await db.commit()

            spatial = await SpatialRiskAdapter().run(
                db,
                event_id=run.event_id,
                spread_run_id=spread.run.run_id,
                threat_buffer_km=run.threat_buffer_km,
            )
            run.spatial_analysis_id = spatial.run.analysis_id
            context = IncidentContext(
                event=EventContext(
                    event_id=event.event_id,
                    name=event.name,
                    status=event.status,
                    scenario_id=event.scenario_id,
                    source_mode=event.source_mode,
                    started_at=event.started_at,
                ),
                candidate=CandidateContext(
                    candidate_id=case.source_candidate_id,
                    visual_case_id=case.visual_case_id,
                    observed_at=case.observed_at,
                    longitude=case.longitude,
                    latitude=case.latitude,
                    upstream_status=case.upstream_status,
                    visual_status=case.status,
                    imagery_status=case.imagery_status,
                    cluster_point_count=case.cluster_point_count,
                    cluster_mean_confidence=case.cluster_mean_confidence,
                    cluster_max_frp_mw=case.cluster_max_frp_mw,
                ),
                ignition=ignition,
                visual_findings=[],
                weather=weather,
                spread=spread,
                spatial=spatial,
                resource=CapabilityStatus(
                    status="unavailable",
                    reason="scenario_not_confirmed",
                    mode="synthetic",
                ),
                route=CapabilityStatus(
                    status="unavailable",
                    reason="scenario_not_confirmed",
                    mode="synthetic",
                ),
            )
            situation_result = SituationAgent().run(context)
            await _set_stage(
                db,
                run,
                "situation",
                "COMPLETED",
                progress=100,
                message="重新推演后的态势摘要已完成。",
                result_id=run.confirmation_id,
                metadata=situation_result["output"],
            )
            await _set_stage(
                db,
                run,
                "spatial_risk",
                "COMPLETED",
                progress=100,
                message="新的空间风险与影响分析已完成。",
                result_id=spatial.run.analysis_id,
                metadata={
                    "summary": spatial.run.summary,
                    "warnings": spatial.run.warnings,
                    "is_simulated": spatial.run.is_simulated,
                    "rerun_from_spread_run_id": (
                        dict(run.metadata_json or {})
                        .get("last_invalidated_results", {})
                        .get("spread_run_id")
                    ),
                },
            )
            await db.commit()
            await generate_scenario(
                db,
                run.workflow_run_id,
                ScenarioGenerateRequest(mode="RECOMMENDED"),
            )
        except Exception as exc:
            await db.rollback()
            run = await _run_or_404(db, workflow_run_id)
            current = (
                run.current_stage
                if run.current_stage in {"situation", "spread", "spatial_risk"}
                else "spread"
            )
            run.status = "FAILED"
            run.error = str(exc)
            await _set_stage(
                db,
                run,
                current,
                "FAILED",
                progress=100,
                message="重新推演阶段失败，可检查参数后重试。",
                error=str(exc),
            )
            await db.commit()


async def generate_scenario(
    db: AsyncSession,
    workflow_run_id: str,
    request: ScenarioGenerateRequest,
) -> EmergencyScenario:
    run = await _run_or_404(db, workflow_run_id)
    if not run.spread_run_id or not run.confirmation_id:
        raise HTTPException(status_code=409, detail="Spread and confirmed fire point are required")
    spread = await db.scalar(select(SimulationRun).where(SimulationRun.run_id == run.spread_run_id))
    confirmation = await db.scalar(
        select(FireConfirmationRecord).where(FireConfirmationRecord.confirmation_id == run.confirmation_id)
    )
    if spread is None or confirmation is None:
        raise HTTPException(status_code=409, detail="Workflow spread or confirmation record is missing")
    await _set_stage(db, run, "scenario", "RUNNING", progress=30, message="正在按内部 provisional 规则生成安全候选点。")
    blueprint = ScenarioRecommendationService().generate(
        event_id=run.event_id,
        ignition=(confirmation.longitude, confirmation.latitude),
        max_radius_km=spread.max_radius_km,
        final_area_km2=spread.final_area_km2,
        spread_direction_deg=spread.spread_direction_deg,
        risk_level=spread.risk_level,
        mode=request.mode,
        manual={
            "command_post": request.command_post,
            "staging_area": request.staging_area,
            "resource_points": request.resource_points,
        },
    )
    scenario_id = f"scn_{uuid4().hex[:18]}"
    scenario = EmergencyScenario(
        scenario_id=scenario_id, workflow_run_id=run.workflow_run_id, event_id=run.event_id,
        mode=request.mode, source="manual" if request.mode == "MANUAL" else "recommended",
        rule_version=RULE_VERSION, size_class=blueprint["size_class"], status="draft", confirmed=False,
        summary={
            "fire_edge_radius_km": blueprint["fire_edge_radius_km"],
            "fire_exclusion_radius_km": blueprint["fire_exclusion_radius_km"],
            "safety_margin_km": blueprint["safety_margin_km"],
            "spread_direction_deg": blueprint["spread_direction_deg"],
            "missing_data": blueprint["missing_data"], "limitations": blueprint["limitations"],
            "rescue_situation": blueprint["rescue_situation"],
            "resource_inventory": blueprint["resource_inventory"],
            "network_points": blueprint["network_points"], "network_links": blueprint["network_links"],
            "operations_node_id": blueprint["operations_node_id"],
            "operation_approach_node_id": blueprint["operation_approach_node_id"],
            "command_node_id": blueprint["command_node_id"], "staging_node_id": blueprint["staging_node_id"],
            "team_node_ids": blueprint["team_node_ids"],
            "protected_target_node_id": blueprint["protected_target_node_id"],
            "ignition": blueprint["ignition"],
        },
        metadata_json={"deterministic_key": f"{run.event_id}:{RULE_VERSION}", "exercise_label": "内部演练场景"},
    )
    db.add(scenario)
    await db.flush()
    for item in blueprint["locations"]:
        db.add(
            ScenarioLocation(
                location_id=f"{scenario_id}-{item['location_type']}-{item['rank']}", scenario_id=scenario_id,
                location_type=item["location_type"], rank=item["rank"], longitude=item["longitude"], latitude=item["latitude"],
                source=item["source"], selected=item["selected"], score=item["score"], evidence=item["evidence"],
                reason=item["reason"], missing_data=item["missing_data"], limitations=item["limitations"],
                metadata_json={"deterministic_location_id": item["location_id"], **item.get("metadata", {})},
            )
        )
    for index, item in enumerate(blueprint["resources"], start=1):
        db.add(
            ScenarioResource(
                resource_id=f"{scenario_id}-{item['resource_type']}-{index}", scenario_id=scenario_id,
                resource_type=item["resource_type"], name=item["name"], longitude=item["longitude"], latitude=item["latitude"],
                status=item["status"], capabilities=item["capabilities"], capacity=item["capacity"], quantity=item["quantity"],
                readiness=item["readiness"], mobility_mode=item["mobility_mode"], mode="SCENARIO",
                metadata_json={**item["metadata"], "node_id": item["node_id"], "team_node_id": item.get("team_node_id")},
            )
        )
    run.scenario_id = scenario_id
    run.status = "WAITING_FOR_INPUT"
    await _set_stage(
        db, run, "scenario", "WAITING_FOR_INPUT", progress=80,
        message="应急场景候选已生成，等待人工选择并确认。", result_id=scenario_id,
        metadata={"mode": request.mode, "rule_version": RULE_VERSION, "size_class": blueprint["size_class"], "candidate_count": len(blueprint["locations"])},
    )
    await db.commit()
    await db.refresh(scenario)
    return scenario


async def confirm_scenario(
    db: AsyncSession,
    workflow_run_id: str,
    request: ScenarioConfirmRequest,
) -> EmergencyScenario:
    run = await _run_or_404(db, workflow_run_id)
    if not run.scenario_id:
        raise HTTPException(status_code=409, detail="Scenario has not been generated")
    scenario = await db.scalar(select(EmergencyScenario).where(EmergencyScenario.scenario_id == run.scenario_id))
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    locations = (
        await db.execute(select(ScenarioLocation).where(ScenarioLocation.scenario_id == scenario.scenario_id))
    ).scalars().all()
    if request.command_location_id:
        if not any(item.location_id == request.command_location_id and item.location_type == "command_post" for item in locations):
            raise HTTPException(status_code=422, detail="Invalid command location")
        for item in locations:
            if item.location_type == "command_post":
                item.selected = item.location_id == request.command_location_id
    if request.staging_location_id:
        if not any(item.location_id == request.staging_location_id and item.location_type == "staging_area" for item in locations):
            raise HTTPException(status_code=422, detail="Invalid staging location")
        for item in locations:
            if item.location_type == "staging_area":
                item.selected = item.location_id == request.staging_location_id
    if not any(item.selected and item.location_type == "command_post" for item in locations):
        raise HTTPException(status_code=422, detail="A command post must be selected")
    if not any(item.selected and item.location_type == "staging_area" for item in locations):
        raise HTTPException(status_code=422, detail="A staging area must be selected")
    scenario.confirmed = True
    scenario.status = "confirmed"
    scenario.confirmed_at = _now()
    scenario.metadata_json = {**scenario.metadata_json, "confirmation_note": request.note, "human_confirmed": True}
    run.status = "RUNNING" if request.run_downstream else "WAITING_FOR_INPUT"
    await _set_stage(db, run, "scenario", "COMPLETED", progress=100, message="人工已确认应急演练场景。", result_id=scenario.scenario_id, metadata={"mode": scenario.mode, "confirmed": True, "rule_version": scenario.rule_version})
    if request.run_downstream:
        await _set_stage(db, run, "resource_dispatch", "READY", progress=0, message="场景库存已确认，可开始 ResourceAgent。")
    await db.commit()
    await db.refresh(scenario)
    return scenario


async def _scenario_blueprint(db: AsyncSession, scenario: EmergencyScenario) -> dict[str, Any]:
    resources = (
        await db.execute(select(ScenarioResource).where(ScenarioResource.scenario_id == scenario.scenario_id).order_by(ScenarioResource.id))
    ).scalars().all()
    return {
        **scenario.summary,
        "resources": [
            {
                "resource_id": item.resource_id, "node_id": item.metadata_json.get("node_id"),
                "resource_type": item.resource_type, "name": item.name, "longitude": item.longitude,
                "latitude": item.latitude, "status": item.status, "capabilities": item.capabilities,
                "capacity": item.capacity, "quantity": item.quantity, "readiness": item.readiness,
                "mobility_mode": item.mobility_mode, "metadata": item.metadata_json,
            }
            for item in resources
        ],
    }


async def execute_downstream(workflow_run_id: str) -> None:
    async with AsyncSessionLocal() as db:
        run = await _run_or_404(db, workflow_run_id)
        scenario = await db.scalar(select(EmergencyScenario).where(EmergencyScenario.scenario_id == run.scenario_id))
        if scenario is None or not scenario.confirmed:
            return
        try:
            run.error = None
            blueprint = await _scenario_blueprint(db, scenario)
            network = ScenarioRoadNetworkProvider().build(blueprint)
            resources = resources_from_blueprint(blueprint)
            await _set_stage(db, run, "resource_dispatch", "RUNNING", progress=35, message="资源调度智能体正在评估演练库存、能力与预计到达时间。")
            await db.commit()
            task = ResourceTask(
                task_id=f"task-{run.workflow_run_id}", task_type="fire_suppression", target_node_id=blueprint["operations_node_id"],
                priority="high", required_capabilities=frozenset({"wildland_suppression"}),
                minimum_resource_requirements=(
                    ResourceRequirement(resource_type="fire_engine", quantity=1, required_capabilities=frozenset({"wildland_suppression"})),
                    ResourceRequirement(resource_type="fire_team", quantity=1, required_capabilities=frozenset({"wildland_suppression"})),
                ),
                strategy="balanced", metadata={"mode": "SCENARIO", "scenario_id": scenario.scenario_id},
            )
            resource_result = ResourceAgent().run(
                ResourceAgentTask(task=task, resources=resources, road_network=network, mode="balanced", incident_id=run.event_id, metadata={"mode": "SCENARIO"})
            )
            resource_plan_id = f"rsp_{uuid4().hex[:18]}"
            db.add(ScenarioResourcePlan(resource_plan_id=resource_plan_id, scenario_id=scenario.scenario_id, workflow_run_id=run.workflow_run_id, mode="SCENARIO", result=resource_result["output"]))
            run.resource_plan_id = resource_plan_id
            await _set_stage(db, run, "resource_dispatch", "COMPLETED", progress=100, message="演练资源调度已完成。", result_id=resource_plan_id, metadata={"mode": "SCENARIO", "summary": resource_result["output"].get("resource_summary"), "shortage": resource_result["output"].get("resource_shortage", [])})
            await _set_stage(db, run, "route_planning", "RUNNING", progress=35, message="路线规划智能体正在计算演练可达性路径。")
            await db.commit()
            route_metadata = {
                "source": "ScenarioRoadNetworkProvider", "mode": "SCENARIO_ROUTE", "synthetic": True,
                "risk_data_source": "空间风险等级与火势预测半径", "start_role": "演练灭火队伍 1", "destination_role": "火场作业接近点",
            }
            route_result = RouteAgent().run(
                RouteTask(
                    road_network=network, start_node_id=blueprint["team_node_ids"][0], destination_node_id=blueprint["operation_approach_node_id"],
                    objective="compare", vehicle="fire_engine", risk_weight=28.0, incident_id=run.event_id,
                    target_name="火场作业接近点", purpose="灭火作业路线",
                    metadata=route_metadata,
                )
            )
            recommended_route = dict(route_result["output"].get("recommended_route") or {})
            if recommended_route:
                recommended_route["metadata"] = {**recommended_route.get("metadata", {}), **route_metadata}
                route_result["output"]["recommended_route"] = recommended_route
            resource_route = recommended_route
            operational_route = {
                **recommended_route,
                "resource_label": "演练灭火队伍 1",
                "eta_minutes": recommended_route.get("estimated_travel_time_minutes"),
            }
            route_plan_id = f"rtp_{uuid4().hex[:18]}"
            db.add(
                ScenarioRoutePlan(
                    route_plan_id=route_plan_id, scenario_id=scenario.scenario_id, workflow_run_id=run.workflow_run_id,
                    mode="SCENARIO_ROUTE", geometry=resource_route.get("geometry") or {}, result=route_result["output"],
                )
            )
            run.route_plan_id = route_plan_id
            await _set_stage(db, run, "route_planning", "COMPLETED", progress=100, message="演练可达性路径已完成；该结果不是实时 OSM 路线。", result_id=route_plan_id, metadata={"mode": "SCENARIO_ROUTE", "summary": route_result["output"].get("route_summary"), "recommended_route": recommended_route})
            await _set_stage(db, run, "commander", "RUNNING", progress=35, message="指挥决策智能体正在汇总上游结果、演练资源和演练路径。")
            await db.commit()
            situation_stage = await _stage(db, run.workflow_run_id, "situation")
            spread_stage = await _stage(db, run.workflow_run_id, "spread")
            risk_stage = await _stage(db, run.workflow_run_id, "spatial_risk")
            analysis_context = AgentAnalysisContext(
                situation=dict(situation_stage.metadata_json),
                spread={"spread_packet": dict(spread_stage.metadata_json), "spread_summary": dict(spread_stage.metadata_json)},
                risk={"risk_packet": dict(risk_stage.metadata_json.get("summary") or {}), "risk_summary": dict(risk_stage.metadata_json.get("summary") or {}), "risk_level": (risk_stage.metadata_json.get("summary") or {}).get("risk_level"), "warnings": risk_stage.metadata_json.get("warnings", [])},
                provenance={
                    "event_id": run.event_id, "candidate_id": run.candidate_id, "visual_case_id": run.visual_case_id,
                    "confirmation_id": run.confirmation_id, "spread_run_id": run.spread_run_id,
                    "spatial_analysis_id": run.spatial_analysis_id, "scenario_id": scenario.scenario_id,
                    "resource_plan_id": resource_plan_id, "route_plan_id": route_plan_id,
                },
                capabilities={"resource": {"status": "completed", "mode": "SCENARIO"}, "route": {"status": "completed", "mode": "SCENARIO_ROUTE"}},
            )
            planning_result = {
                "success": True, "status": "completed", "mode": "SCENARIO_MODE",
                "selected_resources": resource_result["output"].get("selected_resources", []),
                "resource_shortage": resource_result["output"].get("resource_shortage", []),
                "operational_routes": [operational_route] if recommended_route else [],
                "alternative_routes": [item for item in route_result["output"].get("candidate_routes", []) if item is not recommended_route],
                "warnings": ["资源库存和可达性图均为内部演练输入，不代表真实资源或实时道路导航。"],
                "diagnostics": {"scenario_id": scenario.scenario_id, "route_mode": "SCENARIO_ROUTE", "resource_mode": "SCENARIO", "route_start": "演练灭火队伍 1", "route_destination": "火场作业接近点"},
            }
            commander_result = await CommanderAgent().run(analysis_context, planning_result=planning_result)
            commander_output = commander_result["output"]
            decision_run_id = f"dec_{uuid4().hex[:18]}"
            command_plan = dict(commander_output.get("recommended_plan") or {})
            structured = {
                "summary": (commander_output.get("recommendation_packet") or {}).get("summary", ""),
                "priority": command_plan.get("priority"), "actions": command_plan.get("actions", []),
                "evidence": analysis_context.provenance,
                "rules": ["R-CMD-001", "R-CMD-002", "R-RES-001", "R-RTE-002"],
                "warnings": list((commander_output.get("recommendation_packet") or {}).get("warnings") or []),
                "limitations": list(scenario.summary.get("limitations") or []),
                "unavailable_capabilities": ["REAL_ROUTE", "REAL_RESOURCE_INVENTORY", "SENTINEL_CHANGE_DETECTION"],
                "human_confirmation_required": True,
            }
            decision = DecisionRun(
                decision_run_id=decision_run_id, event_id=run.event_id, scenario_id=scenario.scenario_id,
                source_candidate_id=run.candidate_id, visual_case_id=run.visual_case_id, confirmation_id=run.confirmation_id,
                spread_run_id=run.spread_run_id, spatial_analysis_id=run.spatial_analysis_id, status="awaiting_human_confirmation",
                provider=str((commander_output.get("llm") or {}).get("provider") or "structured"),
                model=str((commander_output.get("llm") or {}).get("model") or "structured-command-rules"),
                confidence=0.0, recommended_plan={**command_plan, "structured_output": structured},
                input_summary={"workflow": analysis_context.provenance, "scenario": {"mode": scenario.mode, "rule_version": scenario.rule_version}, "planning": planning_result},
                warnings=structured["warnings"], raw_llm_output=str((commander_output.get("llm") or {}).get("raw_output") or ""),
            )
            db.add(decision)
            await db.flush()
            recommendation_id = f"rec_{uuid4().hex[:18]}"
            db.add(
                RecommendationPackage(
                    package_id=recommendation_id, event_id=run.event_id, decision_run_id=decision_run_id,
                    status="awaiting_human_confirmation", summary=structured["summary"],
                    route_package={"mode": "SCENARIO_ROUTE", "route_plan_id": route_plan_id, "result": route_result["output"]},
                    uav_package={"status": "UNAVAILABLE", "reason": "no_real_uav_asset"},
                    resource_package={"mode": "SCENARIO", "resource_plan_id": resource_plan_id, "result": resource_result["output"]},
                    command_package=structured,
                )
            )
            for name, content in (("resource", resource_result), ("route", route_result), ("commander", commander_result)):
                db.add(AgentPacket(packet_id=f"pkt_{uuid4().hex}", decision_run_id=decision_run_id, event_id=run.event_id, packet_type=name, title=f"{name.title()} workflow output", content=content))
            run.decision_run_id = decision_run_id
            run.recommendation_id = recommendation_id
            run.status = "WAITING_FOR_INPUT"
            await _set_stage(db, run, "commander", "WAITING_FOR_INPUT", progress=90, message="辅助决策已生成，等待人工接受、退回或重新生成。", result_id=decision_run_id, metadata={"decision": structured, "recommendation_id": recommendation_id})
            await db.commit()
        except Exception as exc:
            await db.rollback()
            run = await _run_or_404(db, workflow_run_id)
            current = run.current_stage if run.current_stage in {"resource_dispatch", "route_planning", "commander"} else "resource_dispatch"
            run.status = "FAILED"
            run.error = str(exc)
            await _set_stage(db, run, current, "FAILED", progress=100, message="下游规划阶段失败，可重试。", error=str(exc))
            await db.commit()


async def review_commander(db: AsyncSession, workflow_run_id: str, request: CommanderReviewRequest) -> WorkflowRun:
    run = await _run_or_404(db, workflow_run_id)
    if not run.decision_run_id:
        raise HTTPException(status_code=409, detail="Commander decision is not ready")
    decision = await db.scalar(select(DecisionRun).where(DecisionRun.decision_run_id == run.decision_run_id))
    recommendation = await db.scalar(select(RecommendationPackage).where(RecommendationPackage.package_id == run.recommendation_id))
    if request.action == "approve":
        if decision:
            decision.status = "human_approved"
        if recommendation:
            recommendation.status = "human_approved"
        run.status = "COMPLETED"
        run.error = None
        run.finished_at = _now()
        await _set_stage(db, run, "commander", "COMPLETED", progress=100, message="人工已确认辅助决策方案；未下达真实救援命令。", result_id=run.decision_run_id, metadata={"review_state": "HUMAN_CONFIRMED", "note": request.note})
    elif request.action == "revise":
        if decision:
            decision.status = "revision_requested"
        run.status = "WAITING_FOR_INPUT"
        await _set_stage(db, run, "scenario", "WAITING_FOR_INPUT", progress=80, message="决策已退回场景配置。", result_id=run.scenario_id, metadata={"review_state": "REVISION_REQUESTED", "note": request.note})
    else:
        if decision:
            decision.status = "regeneration_requested"
        run.status = "RUNNING"
        await _set_stage(db, run, "commander", "READY", progress=0, message="已请求重新生成 Commander 建议。", metadata={"review_state": "REGENERATE", "note": request.note})
    await db.commit()
    await db.refresh(run)
    return run


async def latest_workflow(db: AsyncSession, event_id: str) -> WorkflowRun | None:
    return await db.scalar(
        select(WorkflowRun).where(WorkflowRun.event_id == event_id).order_by(desc(WorkflowRun.created_at), desc(WorkflowRun.id)).limit(1)
    )


async def workflow_payload(db: AsyncSession, run: WorkflowRun) -> dict[str, Any]:
    stages = (
        await db.execute(select(WorkflowStageRun).where(WorkflowStageRun.workflow_run_id == run.workflow_run_id).order_by(WorkflowStageRun.id))
    ).scalars().all()
    scenario_payload = None
    artifacts: dict[str, Any] = {}
    if run.confirmation_id:
        confirmation = await db.scalar(select(FireConfirmationRecord).where(FireConfirmationRecord.confirmation_id == run.confirmation_id))
        if confirmation and confirmation.longitude is not None:
            artifacts["confirmed_point"] = {"type": "Point", "coordinates": [confirmation.longitude, confirmation.latitude], "properties": {"confidence": confirmation.confidence, "review_state": run.human_confirmation_state}}
    if run.visual_case_id:
        case = await db.scalar(select(VisualVerificationCaseRecord).where(VisualVerificationCaseRecord.visual_case_id == run.visual_case_id))
        if case:
            artifacts["candidate_point"] = {"type": "Point", "coordinates": [case.longitude, case.latitude], "properties": {"status": case.status, "candidate_id": case.source_candidate_id}}
    if run.spread_run_id:
        steps = (
            await db.execute(select(FireFrontStep).where(FireFrontStep.run_id == run.spread_run_id).order_by(FireFrontStep.time_minute))
        ).scalars().all()
        artifacts["fire_front"] = build_feature_collection(list(steps))
    if run.spatial_analysis_id:
        spatial = await db.scalar(select(SpatialAnalysisRun).where(SpatialAnalysisRun.analysis_id == run.spatial_analysis_id))
        if spatial:
            artifacts["risk"] = spatial.impact_geojson
    if run.scenario_id:
        scenario = await db.scalar(select(EmergencyScenario).where(EmergencyScenario.scenario_id == run.scenario_id))
        if scenario:
            locations = (
                await db.execute(select(ScenarioLocation).where(ScenarioLocation.scenario_id == scenario.scenario_id).order_by(ScenarioLocation.location_type, ScenarioLocation.rank))
            ).scalars().all()
            resources = (
                await db.execute(select(ScenarioResource).where(ScenarioResource.scenario_id == scenario.scenario_id).order_by(ScenarioResource.id))
            ).scalars().all()
            scenario_payload = {
                "scenario_id": scenario.scenario_id, "mode": scenario.mode, "source": scenario.source,
                "status": scenario.status, "rule_version": scenario.rule_version, "size_class": scenario.size_class,
                "confirmed": scenario.confirmed, "summary": scenario.summary,
                "locations": [
                    {"location_id": item.location_id, "type": item.location_type, "rank": item.rank, "longitude": item.longitude, "latitude": item.latitude, "source": item.source, "selected": item.selected, "score": item.score, "evidence": item.evidence, "reason": item.reason, "missing_data": item.missing_data, "limitations": item.limitations, "metadata": item.metadata_json}
                    for item in locations
                ],
                "resources": [
                    {"resource_id": item.resource_id, "type": item.resource_type, "name": item.name, "longitude": item.longitude, "latitude": item.latitude, "status": item.status, "capabilities": item.capabilities, "capacity": item.capacity, "quantity": item.quantity, "readiness": item.readiness, "mobility_mode": item.mobility_mode, "mode": item.mode}
                    for item in resources
                ],
            }
            artifacts["scenario_locations"] = scenario_payload["locations"]
            artifacts["scenario_resources"] = scenario_payload["resources"]
    if run.route_plan_id:
        route = await db.scalar(select(ScenarioRoutePlan).where(ScenarioRoutePlan.route_plan_id == run.route_plan_id))
        if route:
            artifacts["route"] = {"mode": route.mode, "geometry": route.geometry, "result": route.result}
    if run.resource_plan_id:
        resource = await db.scalar(select(ScenarioResourcePlan).where(ScenarioResourcePlan.resource_plan_id == run.resource_plan_id))
        if resource:
            artifacts["resource_plan"] = {"mode": resource.mode, "result": resource.result}
    return {
        "workflow_run_id": run.workflow_run_id, "event_id": run.event_id, "mode": run.mode,
        "status": run.status, "current_stage": run.current_stage, "candidate_id": run.candidate_id,
        "visual_case_id": run.visual_case_id, "confirmation_id": run.confirmation_id,
        "spread_run_id": run.spread_run_id, "spatial_analysis_id": run.spatial_analysis_id,
        "scenario_id": run.scenario_id, "resource_plan_id": run.resource_plan_id,
        "route_plan_id": run.route_plan_id, "decision_run_id": run.decision_run_id,
        "recommendation_id": run.recommendation_id, "human_confirmation_state": run.human_confirmation_state,
        "horizon_minutes": run.horizon_minutes, "threat_buffer_km": run.threat_buffer_km,
        "metadata_json": run.metadata_json, "error": run.error, "created_at": run.created_at,
        "started_at": run.started_at, "finished_at": run.finished_at,
        "stages": [
            {"stage": item.stage, "status": item.status, "progress": item.progress, "message": item.message,
             "result_id": item.result_id, "error": item.error, "metadata_json": item.metadata_json,
             "started_at": item.started_at, "finished_at": item.finished_at}
            for item in stages
        ],
        "scenario": scenario_payload, "artifacts": artifacts,
    }


async def resume_workflow(workflow_run_id: str) -> None:
    async with AsyncSessionLocal() as db:
        run = await _run_or_404(db, workflow_run_id)
        if run.human_confirmation_state == "HUMAN_CONFIRMED" and not run.spread_run_id:
            pass
        elif run.scenario_id:
            scenario = await db.scalar(select(EmergencyScenario).where(EmergencyScenario.scenario_id == run.scenario_id))
            if scenario and scenario.confirmed and not run.decision_run_id:
                await db.close()
                await execute_downstream(workflow_run_id)
                return
            return
        else:
            await db.close()
            await prepare_workflow(workflow_run_id)
            return
    await execute_analysis(workflow_run_id)
