from datetime import datetime, timezone
from io import BytesIO
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.decision import AgentPacket, DecisionRun
from app.models.event import FireEvent
from app.models.observation import EvidenceChain, FusionResult, Observation, TrustedFirePoint
from app.models.recalculation import RecalculationRun
from app.models.recommendation import RecommendationPackage, ResourceInventory, RoutePlan, UavAsset
from app.models.report import DecisionReport
from app.models.scenario import EnvironmentSnapshot
from app.models.spread import FireFrontStep, SimulationRun
from app.schemas.report import ReportCreateRequest
from app.services.decision_service import create_decision_run, latest_decision_run
from app.services.event_service import append_timeline, get_event_or_404
from app.services.recommendation_service import latest_recommendations, regenerate_recommendations
from app.schemas.decision import DecisionRunRequest
from app.schemas.recommendation import RecommendationRegenerateRequest
from app.services.websocket_manager import websocket_manager


def _font_name() -> str:
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        candidates = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simsun.ttc",
            "C:/Windows/Fonts/arial.ttf",
        ]
        for path in candidates:
            try:
                pdfmetrics.registerFont(TTFont("FireReportFont", path))
                return "FireReportFont"
            except Exception:
                continue
    except Exception:
        pass
    return "Helvetica"


def _dt(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value or "")


def _bullet(items: list[str]) -> str:
    if not items:
        return "- None recorded."
    return "\n".join(f"- {item}" for item in items)


async def _latest(db: AsyncSession, model: Any, event_id: str) -> Any | None:
    result = await db.execute(select(model).where(model.event_id == event_id).order_by(desc(model.created_at), desc(model.id)).limit(1))
    return result.scalar_one_or_none()


async def _list(db: AsyncSession, model: Any, event_id: str, limit: int = 50) -> list[Any]:
    result = await db.execute(select(model).where(model.event_id == event_id).order_by(desc(model.created_at), desc(model.id)).limit(limit))
    return list(reversed(result.scalars().all()))


def _event_section(event: FireEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "name": event.name,
        "status": event.status,
        "scenario_id": event.scenario_id,
        "source_mode": event.source_mode,
        "ignition": {
            "longitude": event.ignition_longitude,
            "latitude": event.ignition_latitude,
            "confidence": event.ignition_confidence,
        },
        "started_at": _dt(event.started_at),
    }


def _trusted_section(trusted: TrustedFirePoint | None, fusion: FusionResult | None) -> dict[str, Any]:
    return {
        "trusted_point_id": trusted.trusted_point_id if trusted else "",
        "longitude": trusted.longitude if trusted else None,
        "latitude": trusted.latitude if trusted else None,
        "confidence": trusted.confidence if trusted else None,
        "level": trusted.level if trusted else "",
        "description": trusted.description if trusted else "",
        "fusion_id": fusion.fusion_id if fusion else "",
        "fusion_confidence": fusion.confidence if fusion else None,
        "evidence_count": fusion.evidence_count if fusion else 0,
        "evidence_sources": fusion.evidence_sources if fusion else [],
    }


def _environment_section(env: EnvironmentSnapshot | None) -> dict[str, Any]:
    if not env:
        return {}
    return {
        "time_minute": env.time_minute,
        "temperature_c": env.temperature_c,
        "humidity_percent": env.humidity_percent,
        "wind_speed_m_s": env.wind_speed_m_s,
        "wind_direction_deg": env.wind_direction_deg,
        "fuel_moisture": env.fuel_moisture,
        "fire_weather_index": env.fire_weather_index,
    }


def _spread_section(spread: SimulationRun | None, steps: list[FireFrontStep]) -> dict[str, Any]:
    if not spread:
        return {}
    return {
        "run_id": spread.run_id,
        "engine": spread.engine,
        "forefire_attempted": spread.forefire_attempted,
        "fallback_used": spread.fallback_used,
        "start_minute": spread.start_minute,
        "horizon_minutes": spread.horizon_minutes,
        "step_minutes": spread.step_minutes,
        "final_area_km2": spread.final_area_km2,
        "max_radius_km": spread.max_radius_km,
        "spread_direction_deg": spread.spread_direction_deg,
        "risk_level": spread.risk_level,
        "step_count": len(steps),
        "final_step": {
            "time_minute": steps[-1].time_minute,
            "area_km2": steps[-1].area_km2,
            "radius_km": steps[-1].radius_km,
        }
        if steps
        else {},
    }


def _recommendation_section(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    package: RecommendationPackage = payload["package"]
    routes: list[RoutePlan] = payload.get("routes", [])
    uavs: list[UavAsset] = payload.get("uavs", [])
    resources: list[ResourceInventory] = payload.get("resources", [])
    return {
        "package_id": package.package_id,
        "status": package.status,
        "summary": package.summary,
        "routes": [{"name": item.name, "type": item.route_type, "risk": item.risk, "summary": item.summary} for item in routes],
        "uavs": [{"name": item.name, "status": item.status, "task": item.task} for item in uavs],
        "resources": [
            {"name": item.name, "type": item.resource_type, "quantity": item.quantity, "unit": item.unit, "target": item.target}
            for item in resources
        ],
    }


def _decision_section(run: DecisionRun | None, packets: list[AgentPacket]) -> dict[str, Any]:
    if not run:
        return {}
    plan_packet = next((item.content for item in packets if item.packet_type == "plan_packet"), {})
    return {
        "decision_run_id": run.decision_run_id,
        "provider": run.provider,
        "model": run.model,
        "confidence": run.confidence,
        "recommended_plan": run.recommended_plan,
        "candidate_plans": plan_packet.get("candidate_plans", []),
        "warnings": run.warnings,
    }


def _markdown(sections: dict[str, Any]) -> str:
    event = sections["event_summary"]
    trusted = sections["trusted_fire_point"]
    env = sections["environment_assessment"]
    spread = sections["spread_prediction"]
    decision = sections["decision"]
    recommendation = sections["recommendations"]
    recalculation = sections.get("scenario_recalculation") or {}
    evidence = sections["evidence_chain"]
    lines = [
        f"# {sections['title']}",
        "",
        "## Event Summary",
        f"- Event ID: {event.get('event_id')}",
        f"- Name: {event.get('name')}",
        f"- Scenario: {event.get('scenario_id')}",
        f"- Status: {event.get('status')}",
        f"- Ignition point: {event.get('ignition', {}).get('longitude')}, {event.get('ignition', {}).get('latitude')}",
        "",
        "## Evidence Chain",
        _bullet(
            [
                f"{item.get('source_type')} / {item.get('source_name')} / confidence {item.get('confidence')}"
                for item in evidence.get("observations", [])
            ]
        ),
        "",
        "## Trusted Fire Point",
        f"- Confidence: {trusted.get('confidence')}",
        f"- Level: {trusted.get('level')}",
        f"- Evidence count: {trusted.get('evidence_count')}",
        f"- Sources: {', '.join(trusted.get('evidence_sources') or [])}",
        "",
        "## Environment Assessment",
        f"- Wind: {env.get('wind_speed_m_s')} m/s at {env.get('wind_direction_deg')} degrees",
        f"- Temperature: {env.get('temperature_c')} C",
        f"- Humidity: {env.get('humidity_percent')}%",
        f"- Fire weather index: {env.get('fire_weather_index')}",
        "",
        "## Spread Prediction",
        f"- Engine: {spread.get('engine')}",
        f"- Final area: {spread.get('final_area_km2')} km2",
        f"- Risk level: {spread.get('risk_level')}",
        f"- Horizon: {spread.get('horizon_minutes')} minutes",
        "",
        "## Candidate Plans",
        _bullet([f"{item.get('name')} / score {item.get('score')}" for item in decision.get("candidate_plans", [])]),
        "",
        "## Recommended Plan",
        f"- {decision.get('recommended_plan', {}).get('name') or decision.get('recommended_plan', {}).get('plan_id')}",
        f"- Strategy: {decision.get('recommended_plan', {}).get('strategy', '')}",
        "",
        "## Route, UAV, And Resource Recommendations",
        f"- Recommendation package: {recommendation.get('package_id')}",
        f"- Summary: {recommendation.get('summary')}",
        _bullet([f"Route: {item.get('name')} / {item.get('risk')}" for item in recommendation.get("routes", [])]),
        _bullet([f"UAV: {item.get('name')} / {item.get('status')}" for item in recommendation.get("uavs", [])]),
        _bullet([f"Resource: {item.get('name')} / {item.get('quantity')} {item.get('unit')}" for item in recommendation.get("resources", [])]),
        "",
        "## Scenario Disturbance Recalculation",
        f"- Recalculation ID: {recalculation.get('recalculation_id', '')}",
        f"- Change summary: {recalculation.get('change_summary', {})}",
        "",
        "## Assumptions And Limitations",
        "- This is an early command decision-support report.",
        "- It does not include actual firefighter execution completion, suppression outcome, or post-disaster official investigation conclusions.",
        "- Upstream missing hardware and raw sensor feeds are represented through replaceable processed-data adapters in the current system.",
    ]
    return "\n".join(lines) + "\n"


async def generate_report(db: AsyncSession, event_id: str, request: ReportCreateRequest) -> DecisionReport:
    event = await get_event_or_404(db, event_id)
    decision_data = await latest_decision_run(db, event_id)
    if not decision_data:
        decision_data = await create_decision_run(db, event_id, DecisionRunRequest(include_report=True))
    recommendation_data = await latest_recommendations(db, event_id)
    if not recommendation_data:
        recommendation_data = await regenerate_recommendations(db, event_id, RecommendationRegenerateRequest(status="recommended"))

    observations = await _list(db, Observation, event_id, limit=30)
    evidence = await _list(db, EvidenceChain, event_id, limit=30)
    fusion = await _latest(db, FusionResult, event_id)
    trusted = await _latest(db, TrustedFirePoint, event_id)
    env = await _latest(db, EnvironmentSnapshot, event_id)
    spread = await _latest(db, SimulationRun, event_id)
    steps: list[FireFrontStep] = []
    if spread:
        step_result = await db.execute(select(FireFrontStep).where(FireFrontStep.run_id == spread.run_id).order_by(FireFrontStep.time_minute, FireFrontStep.id))
        steps = list(step_result.scalars().all())
    run: DecisionRun = decision_data["run"]
    packets = decision_data.get("packets") or []
    recalculation = await _latest(db, RecalculationRun, event_id) if request.include_recalculation else None

    sections = {
        "title": "Early Command Decision Support Report",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "event_summary": _event_section(event),
        "evidence_chain": {
            "observations": [
                {
                    "source_type": item.source_type,
                    "source_name": item.source_name,
                    "stage": item.stage,
                    "confidence": item.confidence,
                    "observed_at": _dt(item.observed_at),
                }
                for item in observations
            ],
            "evidence": [
                {"source_type": item.source_type, "reliability": item.reliability, "contribution": item.contribution, "explanation": item.explanation}
                for item in evidence
            ],
        },
        "trusted_fire_point": _trusted_section(trusted, fusion),
        "environment_assessment": _environment_section(env),
        "spread_prediction": _spread_section(spread, steps),
        "decision": _decision_section(run, packets),
        "recommendations": _recommendation_section(recommendation_data),
        "scenario_recalculation": {
            "recalculation_id": recalculation.recalculation_id,
            "disturbance_id": recalculation.disturbance_id,
            "base_package_id": recalculation.base_package_id,
            "new_package_id": recalculation.new_package_id,
            "change_summary": recalculation.change_summary,
        }
        if recalculation
        else {},
        "assumptions_and_limitations": [
            "Early command decision-support only.",
            "No actual firefighter execution completion is represented.",
            "Current upstream hardware gaps are handled by replaceable processed-data adapters.",
        ],
    }
    content = _markdown(sections)
    report = DecisionReport(
        report_id=f"rpt_{uuid4().hex[:18]}",
        event_id=event_id,
        decision_run_id=run.decision_run_id,
        recommendation_package_id=recommendation_data["package"].package_id,
        recalculation_id=recalculation.recalculation_id if recalculation else "",
        title="Early Command Decision Support Report",
        format=request.format,
        summary=f"Early command report for {event.name}; final area {sections['spread_prediction'].get('final_area_km2')} km2.",
        sections=sections,
        content_markdown=content,
    )
    db.add(report)
    await append_timeline(
        db,
        event_id=event_id,
        event_type="report.generated",
        status="reported",
        title="Early command report generated",
        message="A downloadable early command decision-support report has been generated.",
        payload={"report_id": report.report_id, "decision_run_id": run.decision_run_id},
        broadcast=True,
    )
    await db.commit()
    await db.refresh(report)
    await websocket_manager.broadcast_event(event_id, "report.generated", {"report_id": report.report_id})
    return report


async def latest_report(db: AsyncSession, event_id: str) -> DecisionReport | None:
    await get_event_or_404(db, event_id)
    return await _latest(db, DecisionReport, event_id)


async def get_report(db: AsyncSession, report_id: str) -> DecisionReport:
    result = await db.execute(select(DecisionReport).where(DecisionReport.report_id == report_id).limit(1))
    report = result.scalar_one_or_none()
    if not report:
        raise AppError(f"Report not found: {report_id}", code="report_not_found", status_code=404)
    return report


def render_report_pdf(report: DecisionReport) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=report.title,
    )
    font = _font_name()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", fontName=font, fontSize=18, leading=24, spaceAfter=12, textColor=colors.HexColor("#0f172a")))
    styles.add(ParagraphStyle(name="SectionTitle", fontName=font, fontSize=12, leading=16, spaceBefore=10, spaceAfter=6, textColor=colors.HexColor("#1d4ed8")))
    styles.add(ParagraphStyle(name="BodyTextCN", fontName=font, fontSize=9.5, leading=13, spaceAfter=4, textColor=colors.HexColor("#111827")))
    styles.add(ParagraphStyle(name="SmallTextCN", fontName=font, fontSize=8, leading=11, textColor=colors.HexColor("#475569")))

    sections = report.sections or {}
    event = sections.get("event_summary", {})
    trusted = sections.get("trusted_fire_point", {})
    env = sections.get("environment_assessment", {})
    spread = sections.get("spread_prediction", {})
    decision = sections.get("decision", {})
    recommendations = sections.get("recommendations", {})
    recalculation = sections.get("scenario_recalculation", {})
    limitations = sections.get("assumptions_and_limitations", [])

    story: list[Any] = [
        Paragraph(report.title, styles["ReportTitle"]),
        Paragraph(f"Report ID: {report.report_id}", styles["SmallTextCN"]),
        Paragraph(f"Generated at: {_dt(report.created_at)}", styles["SmallTextCN"]),
        Spacer(1, 6),
    ]

    def section(title: str, body: list[str]) -> None:
        story.append(Paragraph(title, styles["SectionTitle"]))
        for item in body:
            story.append(Paragraph(str(item), styles["BodyTextCN"]))

    section(
        "1. Event Summary",
        [
            f"Event: {event.get('name', '')} ({event.get('event_id', '')})",
            f"Scenario: {event.get('scenario_id', '')}; status: {event.get('status', '')}",
            f"Ignition point: {event.get('ignition', {}).get('longitude')}, {event.get('ignition', {}).get('latitude')}; confidence: {event.get('ignition', {}).get('confidence')}",
        ],
    )
    section(
        "2. Trusted Fire Point And Evidence",
        [
            f"Trusted point: {trusted.get('longitude')}, {trusted.get('latitude')}; confidence: {trusted.get('confidence')}; level: {trusted.get('level')}",
            f"Evidence count: {trusted.get('evidence_count')}; sources: {', '.join(trusted.get('evidence_sources') or [])}",
        ],
    )
    section(
        "3. Environment And Spread Prediction",
        [
            f"Wind: {env.get('wind_speed_m_s')} m/s at {env.get('wind_direction_deg')} degrees; FWI: {env.get('fire_weather_index')}",
            f"Spread engine: {spread.get('engine')}; final area: {spread.get('final_area_km2')} km2; risk level: {spread.get('risk_level')}",
        ],
    )
    section(
        "4. Recommended Command Plan",
        [
            f"Provider/model: {decision.get('provider', '')} / {decision.get('model', '')}; confidence: {decision.get('confidence')}",
            f"Recommended plan: {decision.get('recommended_plan', {}).get('name') or decision.get('recommended_plan', {}).get('plan_id')}",
            f"Strategy: {decision.get('recommended_plan', {}).get('strategy', '')}",
        ],
    )

    route_rows = [["Type", "Name", "Risk"]]
    for item in recommendations.get("routes", [])[:6]:
        route_rows.append([item.get("type", ""), item.get("name", ""), item.get("risk", "")])
    if len(route_rows) > 1:
        story.append(Paragraph("5. Route Recommendations", styles["SectionTitle"]))
        table = Table(route_rows, colWidths=[32 * mm, 88 * mm, 32 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), font),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ]
            )
        )
        story.append(table)

    section(
        "6. UAV And Resource Recommendations",
        [
            f"UAV tasks: {len(recommendations.get('uavs', []) or [])}",
            f"Resource allocations: {len(recommendations.get('resources', []) or [])}",
            f"Recommendation package: {recommendations.get('package_id', '')}",
        ],
    )
    if recalculation:
        section(
            "7. Scenario Recalculation",
            [
                f"Recalculation ID: {recalculation.get('recalculation_id', '')}",
                f"Change summary: {recalculation.get('change_summary', {})}",
            ],
        )
    section("8. Assumptions And Limitations", [f"- {item}" for item in limitations])
    doc.build(story)
    return buffer.getvalue()
