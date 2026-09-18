from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents.risk_agent import RiskAgent
from app.agents.situation_agent import SituationAgent
from app.agents.spread_agent import SpreadAgent
from app.db.base import Base
from app.integrations.schemas import (
    CandidateContext,
    CapabilityStatus,
    CommandWorkflowRequest,
    EventContext,
    IncidentContext,
    TrustedIgnition,
)
from app.integrations.spatial_risk import SpatialRiskAdapter
from app.integrations.spread import SpreadAdapter
from app.integrations.trusted_ignition import TrustedIgnitionAdapter
from app.models.decision import DecisionRun
from app.models.event import FireEvent
from app.models.recommendation import RecommendationPackage
from app.schemas.spatial_analysis import (
    SpatialAnalysisPayload,
    SpatialAnalysisRunRead,
)
from app.schemas.spread import (
    FireFrontStepRead,
    SimulationRunRead,
    SpreadEnvironmentFrame,
    SpreadRunPayload,
)
from app.services.command_workflow_service import run_command_workflow
from app.visual_verification.models import (
    FireConfirmationRecord,
    VisualVerificationCaseRecord,
)


NOW = datetime(2021, 7, 14, 9, 10, tzinfo=UTC)
pytestmark = pytest.mark.asyncio


def _ignition() -> TrustedIgnition:
    return TrustedIgnition(
        event_id="dixie_fire_2021",
        confirmation_id="vfc_test",
        visual_case_id="vc_test",
        source_candidate_id="candidate_test",
        longitude=-121.28,
        latitude=40.02,
        observed_at=NOW,
        confirmed_at=NOW,
        confidence=0.91,
        evidence_ids=["finding_fire"],
        confirmation_method="manual_review_fixture",
        is_simulated=True,
    )


def _weather() -> list[SpreadEnvironmentFrame]:
    return [
        SpreadEnvironmentFrame(
            elapsed_minutes=0,
            temperature_c=31,
            humidity_percent=24,
            wind_speed_m_s=5.2,
            wind_direction_deg=225,
            fuel_moisture=0.11,
            fire_weather_index=26,
            source="member_a_hourly_weather",
        ),
        SpreadEnvironmentFrame(
            elapsed_minutes=180,
            temperature_c=32,
            humidity_percent=22,
            wind_speed_m_s=5.8,
            wind_direction_deg=230,
            fuel_moisture=0.1,
            fire_weather_index=29,
            source="member_a_hourly_weather",
        ),
    ]


def _spread() -> SpreadRunPayload:
    step = FireFrontStepRead(
        step_id="step_test",
        run_id="spr_test",
        event_id="dixie_fire_2021",
        time_minute=180,
        elapsed_seconds=10800,
        area_km2=2.4,
        radius_km=1.1,
        spread_direction_deg=230,
        fireline_geojson={"type": "Feature", "geometry": {"type": "Polygon", "coordinates": []}},
        created_at=NOW,
    )
    return SpreadRunPayload(
        run=SimulationRunRead(
            run_id="spr_test",
            event_id="dixie_fire_2021",
            scenario_id="dixie_fire_2021",
            status="completed",
            engine="raster_agent_tool",
            forefire_attempted=False,
            forefire_available=False,
            fallback_used=False,
            start_minute=0,
            horizon_minutes=180,
            step_minutes=60,
            ignition_longitude=-121.28,
            ignition_latitude=40.02,
            final_area_km2=2.4,
            max_radius_km=1.1,
            spread_direction_deg=230,
            risk_level="high",
            input_snapshot={"ignition_point": {"input_source": "visual_confirmation:vfc_test"}},
            result_summary={},
            error_message="",
            created_at=NOW,
        ),
        steps=[step],
        geojson={"type": "FeatureCollection", "features": []},
    )


def _spatial() -> SpatialAnalysisPayload:
    return SpatialAnalysisPayload(
        run=SpatialAnalysisRunRead(
            analysis_id="spa_test",
            event_id="dixie_fire_2021",
            spread_run_id="spr_test",
            status="completed",
            analysis_engine="python_geometry_astar",
            input_source="agent_spread:spr_test",
            summary={
                "risk_areas": {"high_count": 2, "medium_count": 1, "low_count": 0},
                "affected_object_count": 0,
            },
            parameters={},
            impact_geojson={"type": "FeatureCollection", "features": []},
            route_geojson={"type": "FeatureCollection", "features": []},
            warnings=[],
            is_simulated=False,
            created_at=NOW,
        ),
        impacts=[],
        routes=[],
    )


def _incident() -> IncidentContext:
    return IncidentContext(
        event=EventContext(
            event_id="dixie_fire_2021",
            name="Dixie Fire",
            status="confirmed",
            scenario_id="dixie_fire_2021",
            source_mode="historical",
            started_at=NOW,
        ),
        candidate=CandidateContext(
            candidate_id="candidate_test",
            visual_case_id="vc_test",
            observed_at=NOW,
            longitude=-121.28,
            latitude=40.02,
            upstream_status="candidate",
            visual_status="confirmed",
            imagery_status="available",
        ),
        ignition=_ignition(),
        visual_findings=[{"finding_type": "fire", "detected": True}],
        weather=_weather(),
        spread=_spread(),
        spatial=_spatial(),
        resource=CapabilityStatus(status="unavailable", reason="missing_resource_inventory"),
        route=CapabilityStatus(status="unavailable", reason="missing_road_network"),
    )


def _case() -> VisualVerificationCaseRecord:
    return VisualVerificationCaseRecord(
        visual_case_id="vc_test",
        source_candidate_id="candidate_test",
        upstream_schema_version="fire.hotspot.candidate.v0.1",
        upstream_status="candidate",
        event_id="dixie_fire_2021",
        event_name="Dixie Fire",
        observed_at=NOW,
        longitude=-121.28,
        latitude=40.02,
        imagery_status="available",
        data_owner={"member": "A"},
        replay_metadata={"is_replay": True},
        product_fields={},
        upstream_payload_hash="0" * 64,
        status="confirmed",
        version=1,
        is_simulated=True,
    )


async def _database():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def test_confirmed_point_becomes_trusted_ignition() -> None:
    engine, sessions = await _database()
    async with sessions() as db:
        db.add(_case())
        db.add(
            FireConfirmationRecord(
                confirmation_id="vfc_test",
                visual_case_id="vc_test",
                source_candidate_id="candidate_test",
                version=1,
                is_current=True,
                status="confirmed",
                confidence=0.91,
                reason_codes=["manual_review"],
                evidence_ids=["finding_fire"],
                longitude=-121.28,
                latitude=40.02,
                confirmation_method="manual_review_fixture",
                rule_version="test-v1",
                confirmed_at=NOW,
                is_simulated=True,
            )
        )
        await db.commit()
        result = await TrustedIgnitionAdapter().resolve(
            db, event_id="dixie_fire_2021", confirmation_id="vfc_test"
        )
        assert result.source == "visual_fire_confirmation"
        assert result.longitude == -121.28
        assert result.visual_case_id == "vc_test"
    await engine.dispose()


async def test_spread_and_spatial_adapters_call_member_c_services() -> None:
    spread_data = {
        "run": _spread().run,
        "steps": _spread().steps,
        "geojson": _spread().geojson,
    }
    with (
        patch("app.integrations.spread.load_hourly_weather", AsyncMock(return_value=_weather())),
        patch("app.integrations.spread.create_spread_run", AsyncMock(return_value=spread_data)) as spread_call,
    ):
        payload, weather = await SpreadAdapter().run(
            AsyncMock(),
            event_id="dixie_fire_2021",
            ignition=_ignition(),
            horizon_minutes=180,
        )
    request = spread_call.await_args.args[2]
    assert request.input_source == "visual_confirmation:vfc_test"
    assert request.ignition_point.longitude == -121.28
    assert payload.run.engine == "raster_agent_tool"
    assert weather[0].source == "member_a_hourly_weather"

    spatial_data = {"run": _spatial().run, "impacts": [], "routes": []}
    with patch(
        "app.integrations.spatial_risk.create_spatial_analysis",
        AsyncMock(return_value=spatial_data),
    ) as spatial_call:
        spatial = await SpatialRiskAdapter().run(
            AsyncMock(),
            event_id="dixie_fire_2021",
            spread_run_id="spr_test",
            threat_buffer_km=0.45,
        )
    request = spatial_call.await_args.args[2]
    assert request.input_source == "agent_spread:spr_test"
    assert request.include_routes is False
    assert spatial.run.analysis_id == "spa_test"


async def test_agents_explain_real_results_without_recalculation() -> None:
    context = _incident()
    situation = SituationAgent().run(context)
    spread = SpreadAgent().run(context, {"SituationAgent": situation})
    risk = RiskAgent().run(
        context,
        {"SituationAgent": situation, "SpreadAgent": spread},
    )
    assert situation["output"]["situation_summary"]["confirmed_fire_point"]["confirmation_id"] == "vfc_test"
    assert spread["output"]["spread_summary"]["run_id"] == "spr_test"
    assert risk["output"]["risk_summary"]["analysis_id"] == "spa_test"
    assert risk["output"]["risk_factors"] == ["member_c_spatial_analysis"]


async def test_workflow_persists_complete_id_chain_and_unavailable_capabilities() -> None:
    engine, sessions = await _database()
    async with sessions() as db:
        db.add(
            FireEvent(
                event_id="dixie_fire_2021",
                name="Dixie Fire",
                status="confirmed",
                scenario_id="dixie_fire_2021",
                source_mode="historical",
                ignition_longitude=-121.28,
                ignition_latitude=40.02,
                ignition_confidence=0.91,
                started_at=NOW,
            )
        )
        db.add(_case())
        db.add(
            FireConfirmationRecord(
                confirmation_id="vfc_test",
                visual_case_id="vc_test",
                source_candidate_id="candidate_test",
                version=1,
                is_current=True,
                status="confirmed",
                confidence=0.91,
                reason_codes=["manual_review"],
                evidence_ids=["finding_fire"],
                longitude=-121.28,
                latitude=40.02,
                confirmation_method="manual_review_fixture",
                rule_version="test-v1",
                confirmed_at=NOW,
                is_simulated=True,
            )
        )
        await db.commit()

        provider = SimpleNamespace(
            generate=AsyncMock(
                return_value=SimpleNamespace(
                    provider="test",
                    model="test",
                    content='{"summary":"structured test plan"}',
                    used_remote=False,
                )
            )
        )
        with (
            patch.object(
                SpreadAdapter,
                "run",
                AsyncMock(return_value=(_spread(), _weather())),
            ),
            patch.object(
                SpatialRiskAdapter,
                "run",
                AsyncMock(return_value=_spatial()),
            ),
            patch("app.llm.providers.get_llm_provider", return_value=provider),
        ):
            result = await run_command_workflow(
                db,
                "dixie_fire_2021",
                CommandWorkflowRequest(confirmation_id="vfc_test"),
            )

        assert result.identifiers.confirmation_id == "vfc_test"
        assert result.identifiers.spread_run_id == "spr_test"
        assert result.identifiers.spatial_analysis_id == "spa_test"
        assert result.resource.reason == "missing_resource_inventory"
        assert result.route.reason == "missing_road_network"
        decision = await db.scalar(
            select(DecisionRun).where(
                DecisionRun.decision_run_id == result.identifiers.decision_run_id
            )
        )
        recommendation = await db.scalar(
            select(RecommendationPackage).where(
                RecommendationPackage.package_id == result.identifiers.recommendation_id
            )
        )
        assert decision.confirmation_id == "vfc_test"
        assert decision.spread_run_id == "spr_test"
        assert decision.spatial_analysis_id == "spa_test"
        assert recommendation.decision_run_id == decision.decision_run_id
    await engine.dispose()
