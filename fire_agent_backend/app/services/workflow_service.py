from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.schemas.clock import ClockStartRequest, ClockStepRequest
from app.schemas.decision import DecisionRunRequest
from app.schemas.event import IgnitionPoint, StartSimulatedEventRequest
from app.schemas.recommendation import RecommendationRegenerateRequest
from app.schemas.report import ReportCreateRequest
from app.schemas.spread import SpreadRunRequest
from app.services.decision_service import create_decision_run
from app.services.event_service import create_simulated_event, get_event_or_404
from app.services.historical_event_service import get_historical_event
from app.services.clock_service import pause_clock, start_clock, step_clock
from app.services.recommendation_service import regenerate_recommendations
from app.services.report_service import generate_report
from app.services.spread_service import create_spread_run


async def rerun_spread_workflow(
    db: AsyncSession,
    event_id: str,
    spread_request: SpreadRunRequest,
    *,
    include_report: bool = False,
) -> dict[str, Any]:
    """Run the dependent decision chain after an operator changes spread inputs."""
    await get_event_or_404(db, event_id)
    spread = await create_spread_run(db, event_id, spread_request)
    decision = await create_decision_run(db, event_id, DecisionRunRequest(include_report=include_report))
    recommendations = await regenerate_recommendations(
        db,
        event_id,
        RecommendationRegenerateRequest(status="recommended"),
    )
    report = await generate_report(db, event_id, ReportCreateRequest()) if include_report else None
    return {
        "schema_version": "fire.workflow.rerun-spread.v0.1",
        "event_id": event_id,
        "spread": spread,
        "decision": decision,
        "recommendations": recommendations,
        "report": report,
        "source_modes": {
            "environment_override": "user_input" if spread_request.user_environment_override else "workflow_environment_snapshot",
            "spread": "model_result",
            "risk_route_resource_commander": "model_result",
            "report": "model_result" if include_report else "not_requested",
        },
    }


async def start_historical_fire_workflow(
    db: AsyncSession,
    historical_event_id: str,
    *,
    include_report: bool = True,
) -> dict[str, Any]:
    """Start the existing workflow runtime for a locally supported historical event.

    Historical catalog data is real, while the current evidence-runtime adapters are
    explicitly tagged as drill data. This distinction is returned to the client.
    """
    historical = await get_historical_event(db, historical_event_id)
    local_event_id = (historical.data_availability or {}).get("local_event_id")
    if not local_event_id:
        raise AppError(
            "This historical event is catalog metadata only and has no registered local workflow data package.",
            code="historical_workflow_data_unavailable",
            status_code=409,
        )

    event = await create_simulated_event(
        db,
        StartSimulatedEventRequest(
            scenario_id="dixie_fire_2021_replay",
            name=f"{historical.name} historical workflow replay",
            ignition_point=IgnitionPoint(
                longitude=historical.centroid_longitude,
                latitude=historical.centroid_latitude,
                confidence=0.92,
            ),
            metadata={
                "historical_event_id": historical.event_id,
                "historical_data_source": historical.source_citation,
                "historical_catalog_mode": "real_data",
                "workflow_observation_mode": "drill_data",
            },
        ),
    )
    await start_clock(db, event.event_id, ClockStartRequest(tick_interval_seconds=30, reset=True))
    await pause_clock(db, event.event_id)
    for _ in range(6):
        await step_clock(db, event.event_id, ClockStepRequest(minutes=5))
    workflow = await rerun_spread_workflow(
        db,
        event.event_id,
        SpreadRunRequest(horizon_minutes=120, step_minutes=30, prefer_forefire=True),
        include_report=include_report,
    )
    return {
        "schema_version": "fire.workflow.historical-replay.v0.1",
        "historical_event_id": historical.event_id,
        "event": event,

        "workflow": workflow,
        "source_modes": {
            "historical_catalog": "real_data",
            "firms_weather_dem_fuel_mtbs": "real_data_registered",
            "observation_confirmation": "drill_data",
            "spread_risk_route_resource_commander": "model_result",
            "report": "model_result" if include_report else "not_requested",
        },
    }
