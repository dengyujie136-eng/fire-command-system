import json
import unittest
from pathlib import Path

from fastapi import FastAPI
from pydantic import ValidationError

from app.visual_verification.member_a_adapter import (
    adapt_hotspot_candidate,
    adapt_hotspot_envelope,
    build_visual_case_id,
)
from app.visual_verification.schemas import (
    HotspotCandidate,
    HotspotCandidateEnvelope,
    VisualDecision,
    VisualVerificationOutcome,
)
from app.visual_verification.states import VisualCaseStatus
from app.visual_verification.router import router


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "visual_verification"


def load_json(name: str) -> dict:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as stream:
        return json.load(stream)


class MemberAContractTests(unittest.TestCase):
    def test_unregistered_router_contract_builds(self) -> None:
        app = FastAPI()
        app.include_router(router)
        paths = app.openapi()["paths"]
        self.assertIn("/visual-verification/candidates/import", paths)
        self.assertIn("/visual-verification/candidates", paths)
        self.assertIn("/visual-verification/candidates/{visual_case_id}", paths)

    def test_http_mqtt_batch_envelope_adapts_without_confirming(self) -> None:
        envelope = HotspotCandidateEnvelope.model_validate(load_json("candidate_input.json"))
        cases = adapt_hotspot_envelope(envelope)

        self.assertEqual(len(cases), 3)
        self.assertTrue(all(case.status == VisualCaseStatus.RECEIVED for case in cases))
        self.assertEqual(cases[0].longitude, -121.3821)
        self.assertEqual(
            cases[0].source_asset_ids,
            ["asset-wildfire-smoke", "asset-wildfire-false-color"],
        )

    def test_upstream_confirmed_status_cannot_bypass_visual_verification(self) -> None:
        payload = load_json("member_a_historical_candidate.json")
        payload["status"] = "confirmed"
        candidate = HotspotCandidate.model_validate(payload)
        case = adapt_hotspot_candidate(candidate)
        self.assertEqual(case.status, VisualCaseStatus.RECEIVED)

    def test_candidate_identifier_is_preserved_and_internal_id_is_bounded(self) -> None:
        candidate = HotspotCandidate.model_validate(
            load_json("member_a_historical_candidate.json")
        )
        case = adapt_hotspot_candidate(candidate)
        self.assertEqual(case.source_candidate_id, candidate.candidate_id)
        self.assertEqual(case.visual_case_id, build_visual_case_id(candidate.candidate_id))
        self.assertLessEqual(len(case.visual_case_id), 180)

    def test_envelope_rejects_duplicate_candidate_identifiers(self) -> None:
        payload = load_json("candidate_input.json")
        payload["candidates"].append(payload["candidates"][0])
        with self.assertRaises(ValidationError):
            HotspotCandidateEnvelope.model_validate(payload)

    def test_envelope_rejects_candidate_from_another_event(self) -> None:
        payload = load_json("candidate_input.json")
        payload["candidates"][0]["event_id"] = "another-event"
        with self.assertRaises(ValidationError):
            HotspotCandidateEnvelope.model_validate(payload)

    def test_firms_candidate_identifier_must_follow_fixed_rule(self) -> None:
        payload = load_json("member_a_historical_candidate.json")
        payload["candidate_id"] = "dixie_fire_2021-row-17"
        with self.assertRaises(ValidationError):
            HotspotCandidate.model_validate(payload)

    def test_upstream_times_must_be_utc(self) -> None:
        payload = load_json("member_a_historical_candidate.json")
        payload["observed_at"] = "2021-07-13T17:30:00+08:00"
        with self.assertRaises(ValidationError):
            HotspotCandidate.model_validate(payload)

    def test_orchestration_outcome_contains_required_fields(self) -> None:
        outcome = VisualVerificationOutcome(
            candidate_id="candidate-001",
            analysis_run_id="run-001",
            fire=True,
            confidence=0.92,
            reason="Visible flame and smoke evidence agree.",
            evidence_refs=["asset-001"],
            decision=VisualDecision.CONFIRMED,
            recommended_upstream_status="confirmed",
            is_simulated=True,
        )
        self.assertTrue(outcome.fire)

    def test_uncertain_outcome_cannot_recommend_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            VisualVerificationOutcome(
                candidate_id="candidate-001",
                analysis_run_id="run-001",
                fire=None,
                confidence=0.4,
                reason="No usable imagery.",
                evidence_refs=["asset-001"],
                decision=VisualDecision.UNCERTAIN,
                recommended_upstream_status="rejected",
                is_simulated=True,
            )
