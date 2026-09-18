from typing import Any
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import MultiAgentOrchestrator
from app.integrations.schemas import (
    CandidateContext,
    CapabilityStatus,
    CommandWorkflowRequest,
    CommandWorkflowResult,
    EventContext,
    IncidentContext,
    WorkflowIdentifiers,
)
from app.integrations.spatial_risk import SpatialRiskAdapter
from app.integrations.spread import SpreadAdapter
from app.integrations.trusted_ignition import TrustedIgnitionAdapter
from app.models.decision import AgentPacket, DecisionRun
from app.models.recommendation import RecommendationPackage
from app.services.event_service import append_timeline, get_event_or_404
from app.services.websocket_manager import websocket_manager
from app.visual_verification.models import (
    VisualAnalysisRunRecord,
    VisualFindingRecord,
    VisualVerificationCaseRecord,
)


async def _candidate_context(
    db: AsyncSession,
    visual_case_id: str,
) -> tuple[VisualVerificationCaseRecord, CandidateContext]:
    case = await db.scalar(
        select(VisualVerificationCaseRecord).where(
            VisualVerificationCaseRecord.visual_case_id == visual_case_id
        )
    )
    if case is None:
        raise RuntimeError(f"Visual case not found: {visual_case_id}")
    return case, CandidateContext(
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
    )


async def _visual_findings(
    db: AsyncSession,
    visual_case_id: str,
) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(VisualFindingRecord)
            .join(
                VisualAnalysisRunRecord,
                VisualFindingRecord.analysis_run_id
                == VisualAnalysisRunRecord.analysis_run_id,
            )
            .where(VisualAnalysisRunRecord.visual_case_id == visual_case_id)
            .order_by(desc(VisualFindingRecord.created_at))
            .limit(30)
        )
    ).scalars()
    return [
        {
            "finding_id": item.finding_id,
            "finding_type": item.finding_type,
            "detected": item.detected,
            "confidence": item.confidence,
            "evidence_source": item.evidence_source,
        }
        for item in rows
    ]


def _capability_statuses() -> tuple[CapabilityStatus, CapabilityStatus]:
    return (
        CapabilityStatus(
            status="unavailable",
            reason="missing_resource_inventory",
            source="no_real_inventory_adapter_configured",
        ),
        CapabilityStatus(
            status="unavailable",
            reason="missing_road_network",
            source="no_valid_osm_graph_available",
        ),
    )


async def _persist_decision(
    db: AsyncSession,
    *,
    context: IncidentContext,
    orchestration: dict[str, Any],
) -> tuple[DecisionRun, list[AgentPacket], dict[str, Any]]:
    commander = dict((orchestration.get("commander_result") or {}).get("output") or {})
    llm = dict(commander.get("llm") or {})
    plan = dict(commander.get("recommended_plan") or {})
    decision_run_id = f"dec_{uuid4().hex[:18]}"
    provenance = {
        "candidate_id": context.candidate.candidate_id,
        "visual_case_id": context.candidate.visual_case_id,
        "confirmation_id": context.ignition.confirmation_id,
        "spread_run_id": context.spread.run.run_id,
        "spatial_analysis_id": context.spatial.run.analysis_id,
    }
    packages = {
        "situation_packet": orchestration["analysis_context"]["situation"],
        "spread_packet": orchestration["analysis_context"]["spread"],
        "risk_packet": orchestration["analysis_context"]["risk"],
        "resource_status": context.resource.model_dump(),
        "route_status": context.route.model_dump(),
        "plan_packet": commander.get("plan_packet", {}),
        "recommendation_packet": commander.get("recommendation_packet", {}),
    }
    run = DecisionRun(
        decision_run_id=decision_run_id,
        event_id=context.event.event_id,
        scenario_id=context.event.scenario_id,
        source_candidate_id=context.candidate.candidate_id,
        visual_case_id=context.candidate.visual_case_id,
        confirmation_id=context.ignition.confirmation_id,
        spread_run_id=context.spread.run.run_id,
        spatial_analysis_id=context.spatial.run.analysis_id,
        status="completed",
        provider=str(llm.get("provider") or "structured"),
        model=str(llm.get("model") or "structured-command-rules"),
        confidence=context.ignition.confidence,
        recommended_plan=plan,
        input_summary={
            "workflow": provenance,
            "capabilities": {
                "resource": context.resource.model_dump(),
                "route": context.route.model_dump(),
            },
        },
        warnings=list(
            (commander.get("recommendation_packet") or {}).get("warnings") or []
        ),
        raw_llm_output=str(llm.get("raw_output") or ""),
    )
    db.add(run)
    await db.flush()
    packets: list[AgentPacket] = []
    for result in orchestration.get("agent_results", []):
        packet = AgentPacket(
            packet_id=f"pkt_{uuid4().hex}",
            decision_run_id=decision_run_id,
            event_id=context.event.event_id,
            packet_type=str(result.get("agent_name") or "agent").lower(),
            title=f"{result.get('agent_name', 'Agent')} execution",
            content=dict(result),
        )
        db.add(packet)
        packets.append(packet)
    return run, packets, packages


async def _persist_recommendation(
    db: AsyncSession,
    *,
    context: IncidentContext,
    decision: DecisionRun,
    packages: dict[str, Any],
) -> RecommendationPackage:
    package_id = f"rec_{uuid4().hex[:18]}"
    recommendation = dict(packages.get("recommendation_packet") or {})
    item = RecommendationPackage(
        package_id=package_id,
        event_id=context.event.event_id,
        decision_run_id=decision.decision_run_id,
        status="recommended",
        summary=str(recommendation.get("summary") or "Structured command plan ready"),
        route_package=context.route.model_dump(),
        uav_package={"status": "unavailable", "reason": "not_in_phase_one_workflow"},
        resource_package=context.resource.model_dump(),
        command_package={
            "plan": decision.recommended_plan,
            "provenance": decision.input_summary["workflow"],
            "workflow_status": "completed",
        },
    )
    db.add(item)
    await db.flush()
    return item


async def run_command_workflow(
    db: AsyncSession,
    event_id: str,
    request: CommandWorkflowRequest,
) -> CommandWorkflowResult:
    event = await get_event_or_404(db, event_id)
    ignition = await TrustedIgnitionAdapter().resolve(
        db,
        event_id=event_id,
        confirmation_id=request.confirmation_id,
        candidate_id=request.candidate_id,
    )
    _case, candidate = await _candidate_context(db, ignition.visual_case_id)
    findings = await _visual_findings(db, ignition.visual_case_id)
    spread, weather = await SpreadAdapter().run(
        db,
        event_id=event_id,
        ignition=ignition,
        horizon_minutes=request.horizon_minutes,
    )
    spatial = await SpatialRiskAdapter().run(
        db,
        event_id=event_id,
        spread_run_id=spread.run.run_id,
        threat_buffer_km=request.threat_buffer_km,
    )
    resource, route = _capability_statuses()
    context = IncidentContext(
        event=EventContext(
            event_id=event.event_id,
            name=event.name,
            status=event.status,
            scenario_id=event.scenario_id,
            source_mode=event.source_mode,
            started_at=event.started_at,
        ),
        candidate=candidate,
        ignition=ignition,
        visual_findings=findings,
        weather=weather,
        spread=spread,
        spatial=spatial,
        resource=resource,
        route=route,
    )
    orchestration = await MultiAgentOrchestrator().run(
        context,
        force_provider=request.force_provider,
    )
    decision, packets, packages = await _persist_decision(
        db,
        context=context,
        orchestration=orchestration,
    )
    recommendation = await _persist_recommendation(
        db,
        context=context,
        decision=decision,
        packages=packages,
    )
    await append_timeline(
        db,
        event_id=event_id,
        event_type="command_workflow.completed",
        status="deciding",
        title="Unified command workflow completed",
        message="Visual confirmation, spread, spatial risk, and command agents completed.",
        payload={
            **decision.input_summary["workflow"],
            "decision_run_id": decision.decision_run_id,
            "recommendation_id": recommendation.package_id,
        },
        broadcast=True,
    )
    await db.commit()
    await db.refresh(decision)
    await db.refresh(recommendation)
    for packet in packets:
        await db.refresh(packet)
    commander = dict((orchestration.get("commander_result") or {}).get("output") or {})
    result = CommandWorkflowResult(
        workflow_status="completed",
        identifiers=WorkflowIdentifiers(
            candidate_id=candidate.candidate_id,
            visual_case_id=candidate.visual_case_id,
            confirmation_id=ignition.confirmation_id,
            spread_run_id=spread.run.run_id,
            spatial_analysis_id=spatial.run.analysis_id,
            decision_run_id=decision.decision_run_id,
            recommendation_id=recommendation.package_id,
        ),
        confirmed_point=ignition,
        situation=orchestration["analysis_context"]["situation"],
        spread=orchestration["analysis_context"]["spread"],
        spatial_risk=orchestration["analysis_context"]["risk"],
        resource=resource,
        route=route,
        command_plan=dict(commander.get("recommended_plan") or {}),
        recommendation=dict(commander.get("recommendation_packet") or {}),
        agent_results=list(orchestration.get("agent_results") or []),
        warnings=list((commander.get("recommendation_packet") or {}).get("warnings") or []),
    )
    await websocket_manager.broadcast_event(
        event_id,
        "command_workflow.completed",
        result.model_dump(mode="json"),
    )
    return result


async def latest_command_workflow(
    db: AsyncSession,
    event_id: str,
) -> dict[str, Any] | None:
    decision = await db.scalar(
        select(DecisionRun)
        .where(
            DecisionRun.event_id == event_id,
            DecisionRun.confirmation_id.is_not(None),
        )
        .order_by(desc(DecisionRun.created_at), desc(DecisionRun.id))
        .limit(1)
    )
    if decision is None:
        return None
    recommendation = await db.scalar(
        select(RecommendationPackage)
        .where(RecommendationPackage.decision_run_id == decision.decision_run_id)
        .order_by(desc(RecommendationPackage.created_at))
        .limit(1)
    )
    return {
        "workflow_status": decision.status,
        "identifiers": {
            **dict(decision.input_summary.get("workflow") or {}),
            "decision_run_id": decision.decision_run_id,
            "recommendation_id": recommendation.package_id if recommendation else None,
        },
        "resource": dict(decision.input_summary.get("capabilities", {}).get("resource") or {}),
        "route": dict(decision.input_summary.get("capabilities", {}).get("route") or {}),
        "command_plan": decision.recommended_plan,
        "recommendation": recommendation.command_package if recommendation else {},
        "warnings": decision.warnings,
    }
