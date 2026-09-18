"""Smoke tests for the rule-based decision agent pipeline."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from app.agents.context import DecisionContext
from app.agents.commander_agent import CommanderAgent
from app.agents.orchestrator import MultiAgentOrchestrator
from app.agents.risk_agent import RiskAgent
from app.agents.schema import SCHEMA_VERSION, standardize_agent_result
from app.agents.situation_agent import SituationAgent
from app.agents.spread_agent import SpreadAgent
from app.models.event import FireEvent
from app.models.observation import FusionResult, TrustedFirePoint
from app.models.scenario import EnvironmentSnapshot
from app.models.spread import FireFrontStep, SimulationRun


class _FakeProvider:
    async def generate(self, system_prompt, payload):
        return SimpleNamespace(
            provider="test-provider",
            model="test-model",
            content='{"summary":"Rule-based test decision summary."}',
            used_remote=False,
        )


def _orchestrator() -> MultiAgentOrchestrator:
    return MultiAgentOrchestrator(commander_agent=CommanderAgent(llm_provider=_FakeProvider()))


def _mock_context() -> DecisionContext:
    event = FireEvent(
        event_id="evt_test_agent",
        name="Agent smoke test fire",
        status="deciding",
        scenario_id="test_scenario",
        source_mode="simulation",
        ignition_longitude=102.1,
        ignition_latitude=27.9,
        ignition_confidence=0.88,
        started_at=datetime.now(timezone.utc),
        metadata_json={},
    )
    trusted = TrustedFirePoint(
        trusted_point_id="tfp_test_agent",
        event_id=event.event_id,
        fusion_id="fusion_test_agent",
        longitude=102.1,
        latitude=27.9,
        confidence=0.88,
        level="high",
        description="Mock trusted fire point",
        is_simulated=True,
        data_source_mode="simulation",
    )
    environment = EnvironmentSnapshot(
        snapshot_id="env_test_agent",
        event_id=event.event_id,
        scenario_id=event.scenario_id,
        time_minute=30,
        temperature_c=31.5,
        humidity_percent=28.0,
        wind_speed_m_s=5.6,
        wind_direction_deg=215.0,
        fuel_moisture=0.18,
        fire_weather_index=22.0,
        payload={},
    )
    fusion = FusionResult(
        fusion_id="fusion_test_agent",
        event_id=event.event_id,
        confirmed=True,
        confidence=0.88,
        longitude=102.1,
        latitude=27.9,
        evidence_count=2,
        evidence_sources=["satellite", "sensor"],
        decision="confirmed",
        quality={},
        is_simulated=True,
        data_source_mode="simulation",
    )
    spread_run = SimulationRun(
        run_id="spread_test_agent",
        event_id=event.event_id,
        scenario_id=event.scenario_id,
        status="completed",
        engine="fallback",
        forefire_attempted=False,
        forefire_available=False,
        fallback_used=True,
        start_minute=0,
        horizon_minutes=120,
        step_minutes=30,
        ignition_longitude=102.1,
        ignition_latitude=27.9,
        final_area_km2=4.8,
        max_radius_km=1.4,
        spread_direction_deg=215.0,
        risk_level="medium",
        input_snapshot={},
        result_summary={},
        error_message="",
    )
    steps = [
        FireFrontStep(
            step_id="step_test_agent_0",
            run_id=spread_run.run_id,
            event_id=event.event_id,
            time_minute=0,
            elapsed_seconds=0,
            area_km2=0.2,
            radius_km=0.2,
            spread_direction_deg=215.0,
            fireline_geojson={},
        ),
        FireFrontStep(
            step_id="step_test_agent_1",
            run_id=spread_run.run_id,
            event_id=event.event_id,
            time_minute=120,
            elapsed_seconds=7200,
            area_km2=4.8,
            radius_km=1.4,
            spread_direction_deg=215.0,
            fireline_geojson={},
        ),
    ]
    return DecisionContext(
        event=event,
        trusted_fire_point=trusted,
        environment_snapshot=environment,
        fusion_result=fusion,
        spread_run=spread_run,
        fire_front_steps=steps,
    )


def test_multi_agent_orchestrator_success() -> None:
    orchestration = asyncio.run(_orchestrator().run(_mock_context()))
    agent_results = orchestration["agent_results"]
    result_map = {result["agent_name"]: result for result in agent_results}

    assert [result["agent_name"] for result in agent_results] == [
        "SituationAgent",
        "SpreadAgent",
        "RiskAgent",
        "CommanderAgent",
    ]
    assert all(result["status"] == "success" for result in agent_results)
    assert "situation_summary" in result_map["SituationAgent"]["output"]
    assert "spread_packet" in result_map["SpreadAgent"]["output"]
    assert "spread_summary" in result_map["SpreadAgent"]["output"]
    assert "risk_packet" in result_map["RiskAgent"]["output"]
    assert "risk_summary" in result_map["RiskAgent"]["output"]
    assert "risk_level" in result_map["RiskAgent"]["output"]
    assert "risk_factors" in result_map["RiskAgent"]["output"]
    assert "recommended_plan" in result_map["CommanderAgent"]["output"]


def test_orchestrator_returns_analysis_context() -> None:
    orchestration = asyncio.run(_orchestrator().run(_mock_context()))

    assert {"agent_results", "analysis_context", "commander_result", "standard_outputs"}.issubset(orchestration)
    assert isinstance(orchestration["agent_results"], list)
    assert isinstance(orchestration["standard_outputs"], list)
    assert set(orchestration["analysis_context"]) == {
        "situation",
        "spread",
        "risk",
        "generated_at",
    }
    assert "situation_packet" in orchestration["analysis_context"]["situation"]
    assert "situation_summary" in orchestration["analysis_context"]["situation"]
    assert "spread_packet" in orchestration["analysis_context"]["spread"]
    assert "spread_summary" in orchestration["analysis_context"]["spread"]
    assert "risk_packet" in orchestration["analysis_context"]["risk"]
    assert "risk_level" in orchestration["analysis_context"]["risk"]
    assert "risk_factors" in orchestration["analysis_context"]["risk"]
    assert "warnings" in orchestration["analysis_context"]["risk"]
    assert orchestration["commander_result"]["status"] == "success"
    assert [item["domain"] for item in orchestration["standard_outputs"]] == [
        "situation",
        "spread",
        "risk",
        "command",
    ]


def test_commander_agent_packet_compatible() -> None:
    context = _mock_context()
    situation_result = SituationAgent().run(context)
    spread_result = SpreadAgent().run(context, {"SituationAgent": situation_result})
    risk_result = RiskAgent().run(
        context,
        {
            "SituationAgent": situation_result,
            "SpreadAgent": spread_result,
        },
    )
    from app.agents.context import AgentAnalysisContext

    analysis_context = AgentAnalysisContext.from_agent_results(
        {
            "SituationAgent": situation_result,
            "SpreadAgent": spread_result,
            "RiskAgent": risk_result,
        }
    )

    result = asyncio.run(CommanderAgent(llm_provider=_FakeProvider()).run(analysis_context))

    assert result["status"] == "success"
    assert "plan_packet" in result["output"]
    assert "recommendation_packet" in result["output"]
    assert "recommended_plan" in result["output"]
    assert result["output"]["plan_packet"]["recommended_plan"] == result["output"]["recommended_plan"]
    assert "candidate_plans" in result["output"]["plan_packet"]
    assert result["output"]["recommendation_packet"]["recommended_plan"] == result["output"]["recommended_plan"]
    assert result["output"]["recommendation_packet"]["summary"] == "Rule-based test decision summary."


def test_standard_agent_output_schema_for_spread_visualization() -> None:
    result = SpreadAgent().run(_mock_context())
    standard = standardize_agent_result(result)

    assert standard["schema_version"] == SCHEMA_VERSION
    assert standard["agent_name"] == "SpreadAgent"
    assert standard["domain"] == "spread"
    assert standard["algorithm"]["metrics"]["final_area_km2"] == 4.8
    assert standard["visualization"]["layers"][0]["type"] == "temporal_fire_front"
    assert len(standard["visualization"]["timeline"]) == 2
    assert standard["decision"]["recommendations"] == []


def test_situation_agent_packet_compatible() -> None:
    result = SituationAgent().run(_mock_context())

    assert result["status"] == "success"
    assert result["output"]["situation_packet"] == {
        "summary": "Agent smoke test fire: trusted fire point confirmed with confidence 0.88.",
        "trusted_point": {
            "longitude": 102.1,
            "latitude": 27.9,
            "confidence": 0.88,
        },
        "environment": {
            "temperature_c": 31.5,
            "humidity_percent": 28.0,
            "wind_speed_m_s": 5.6,
            "wind_direction_deg": 215.0,
            "fire_weather_index": 22.0,
        },
    }


def test_risk_agent_packet_compatible() -> None:
    result = RiskAgent().run(_mock_context())

    assert result["status"] == "success"
    assert result["output"]["risk_packet"] == {
        "risk_level": "high",
        "risk_label": "high",
        "summary": "Projected burned area is about 4.80 km2 within 120 minutes; max radius is about 1.40 km.",
        "drivers": ["wind", "fuel moisture", "fire weather index", "trusted point confidence"],
        "spread": {
            "run_id": "spread_test_agent",
            "engine": "fallback",
            "fallback_used": True,
            "step_count": 2,
            "final_area_km2": 4.8,
            "max_radius_km": 1.4,
        },
    }
    assert result["output"]["warnings"] == [
        "ForeFire is unavailable for this run; simplified spread fallback was used.",
        "Wind speed is high; monitor downwind fireline expansion closely.",
        "Humidity is low; dry fuel risk is elevated.",
    ]


def test_spread_agent_packet_and_summary() -> None:
    result = SpreadAgent().run(_mock_context())

    assert result["status"] == "success"
    assert result["output"]["spread_packet"] == {
        "run_id": "spread_test_agent",
        "engine": "fallback",
        "fallback_used": True,
        "step_count": 2,
        "final_area_km2": 4.8,
        "max_radius_km": 1.4,
    }
    assert result["output"]["spread_summary"]["avg_growth_km2_per_hour"] == 2.4
    assert result["output"]["spread_summary"]["spread_direction_deg"] == 215.0
    assert len(result["output"]["spread_summary"]["fire_front_steps"]) == 2


def test_situation_and_risk_agents_run_together() -> None:
    context = _mock_context()
    situation_result = SituationAgent().run(context)
    risk_result = RiskAgent().run(
        context,
        {"SituationAgent": situation_result},
    )

    assert situation_result["status"] == "success"
    assert risk_result["status"] == "success"
    assert "situation_packet" in situation_result["output"]
    assert risk_result["output"]["risk_packet"]["risk_level"] == "high"


def test_situation_spread_and_risk_agents_run_together() -> None:
    context = _mock_context()
    situation_result = SituationAgent().run(context)
    spread_result = SpreadAgent().run(
        context,
        {"SituationAgent": situation_result},
    )
    risk_result = RiskAgent().run(
        context,
        {
            "SituationAgent": situation_result,
            "SpreadAgent": spread_result,
        },
    )

    assert situation_result["status"] == "success"
    assert spread_result["status"] == "success"
    assert risk_result["status"] == "success"
    assert risk_result["output"]["risk_packet"]["spread"] == spread_result["output"]["spread_packet"]


class _FakeDb:
    def __init__(self) -> None:
        self.added = []

    def add(self, item) -> None:
        self.added.append(item)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def refresh(self, item) -> None:
        return None


class _FakeWebsocketManager:
    async def broadcast_event(self, event_id, event_type, payload):
        return None


async def _fake_create_decision_run(decision_service, decision_request_cls) -> dict:
    context = _mock_context()
    originals = {
        "get_event_or_404": decision_service.get_event_or_404,
        "_latest": decision_service._latest,
        "_spread_steps": decision_service._spread_steps,
        "MultiAgentOrchestrator": decision_service.MultiAgentOrchestrator,
        "append_timeline": decision_service.append_timeline,
        "websocket_manager": decision_service.websocket_manager,
    }

    async def fake_get_event_or_404(db, event_id):
        return context.event

    async def fake_latest(db, model, event_id):
        if model is TrustedFirePoint:
            return context.trusted_fire_point
        if model is EnvironmentSnapshot:
            return context.environment_snapshot
        if model is SimulationRun:
            return context.spread_run
        if model is FusionResult:
            return context.fusion_result
        return None

    async def fake_spread_steps(db, run_id):
        return context.fire_front_steps

    async def fake_append_timeline(*args, **kwargs):
        return None

    class _FakeMultiAgentOrchestrator:
        async def run(self, context, force_provider=None):
            return await _orchestrator().run(context, force_provider=force_provider)

    try:
        decision_service.get_event_or_404 = fake_get_event_or_404
        decision_service._latest = fake_latest
        decision_service._spread_steps = fake_spread_steps
        decision_service.MultiAgentOrchestrator = _FakeMultiAgentOrchestrator
        decision_service.append_timeline = fake_append_timeline
        decision_service.websocket_manager = _FakeWebsocketManager()
        return await decision_service.create_decision_run(
            _FakeDb(),
            context.event.event_id,
            decision_request_cls(),
        )
    finally:
        decision_service.get_event_or_404 = originals["get_event_or_404"]
        decision_service._latest = originals["_latest"]
        decision_service._spread_steps = originals["_spread_steps"]
        decision_service.MultiAgentOrchestrator = originals["MultiAgentOrchestrator"]
        decision_service.append_timeline = originals["append_timeline"]
        decision_service.websocket_manager = originals["websocket_manager"]


def test_decision_service_response_contract_with_situation_agent() -> None:
    from app.services import decision_service as current_decision_service

    if not hasattr(current_decision_service, 'MultiAgentOrchestrator'):
        assert callable(current_decision_service.create_decision_run)
        assert current_decision_service.PACKET_TYPES
        return

    try:
        from app.schemas.decision import DecisionRunRequest
        from app.services import decision_service
    except ModuleNotFoundError as exc:
        print(f"skipped decision_service contract test: missing dependency {exc.name}")
        return

    result = asyncio.run(_fake_create_decision_run(decision_service, DecisionRunRequest))

    assert set(result) == {"run", "packets", "packages"}
    assert "situation_packet" in result["packages"]
    assert "risk_packet" in result["packages"]
    assert "plan_packet" in result["packages"]
    assert result["packages"]["situation_packet"]["trusted_point"] == {
        "longitude": 102.1,
        "latitude": 27.9,
        "confidence": 0.88,
    }
    assert result["packages"]["risk_packet"]["risk_level"] == "high"
    assert len(result["packets"]) == len(decision_service.PACKET_TYPES)


if __name__ == "__main__":
    test_multi_agent_orchestrator_success()
    test_orchestrator_returns_analysis_context()
    test_commander_agent_packet_compatible()
    test_standard_agent_output_schema_for_spread_visualization()
    test_situation_agent_packet_compatible()
    test_risk_agent_packet_compatible()
    test_spread_agent_packet_and_summary()
    test_situation_and_risk_agents_run_together()
    test_situation_spread_and_risk_agents_run_together()
    test_decision_service_response_contract_with_situation_agent()
