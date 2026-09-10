import unittest
from datetime import UTC, datetime

from pydantic import ValidationError

from app.visual_verification.confirmation_rules import (
    build_confirmed_fire_handoff,
    evaluate_confirmation,
)
from app.visual_verification.providers import SimulatedVisualProvider
from app.visual_verification.schemas import (
    FindingSupport,
    ImageAnalysisRequest,
    ProfessionalDetection,
    VisualAnalysisResult,
    VisualCase,
)
from app.visual_verification.states import (
    InvalidVisualCaseTransition,
    VisualCaseStatus,
    ensure_visual_case_transition,
)


def visual_case() -> VisualCase:
    return VisualCase(
        visual_case_id="visual-case-001",
        source_candidate_id="candidate-001",
        event_id="cresta-dam-demo",
        observed_at=datetime(2026, 9, 9, 10, 20, tzinfo=UTC),
        longitude=-121.37,
        latitude=39.88,
        source_asset_ids=["image-001"],
        is_simulated=True,
    )


def professional(
    support: FindingSupport,
    confidence: float | None = None,
) -> ProfessionalDetection:
    return ProfessionalDetection(
        support=support,
        confidence=confidence,
        evidence_ids=[] if support == FindingSupport.UNAVAILABLE else ["detector-001"],
        summary="deterministic test finding",
    )


class VisualCaseStateTests(unittest.TestCase):
    def test_happy_path_transitions_are_allowed(self) -> None:
        path = [
            VisualCaseStatus.RECEIVED,
            VisualCaseStatus.IMAGERY_SEARCHING,
            VisualCaseStatus.IMAGERY_READY,
            VisualCaseStatus.ANALYZING,
            VisualCaseStatus.CONFIRMED,
        ]
        for current, target in zip(path, path[1:]):
            ensure_visual_case_transition(current, target)

    def test_confirmed_record_is_immutable(self) -> None:
        with self.assertRaises(InvalidVisualCaseTransition):
            ensure_visual_case_transition(
                VisualCaseStatus.CONFIRMED,
                VisualCaseStatus.ANALYZING,
            )

    def test_case_requires_timezone(self) -> None:
        payload = visual_case().model_dump()
        payload["observed_at"] = datetime(2026, 9, 9)
        with self.assertRaises(ValidationError):
            VisualCase.model_validate(payload)


class VisualSchemaTests(unittest.IsolatedAsyncioTestCase):
    async def test_simulated_provider_returns_valid_structured_result(self) -> None:
        result = await SimulatedVisualProvider("confirmed").analyze(
            ImageAnalysisRequest(
                visual_case_id="visual-case-001",
                image_asset_ids=["image-001", "image-001"],
            )
        )
        self.assertTrue(result.fire_detected)
        self.assertEqual(result.used_evidence_ids, ["image-001"])
        self.assertTrue(result.is_fallback)

    def test_invalid_confidence_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            VisualAnalysisResult.model_validate(
                {
                    "analysis_run_id": "run-001",
                    "visual_case_id": "case-001",
                    "fire_detected": True,
                    "flame_detected": True,
                    "smoke_detected": False,
                    "burn_scar_detected": False,
                    "wildfire_likelihood": 1.2,
                    "image_quality": "good",
                    "scene_type": "forest_wildfire",
                    "decision": "confirmed",
                    "reasoning_summary": "fire",
                    "used_evidence_ids": ["image-001"],
                    "model_name": "test",
                    "model_version": "1",
                    "prompt_version": "v1",
                }
            )


class ConfirmationRuleTests(unittest.IsolatedAsyncioTestCase):
    async def test_agreement_confirms_and_builds_handoff(self) -> None:
        result = await SimulatedVisualProvider("confirmed").analyze(
            ImageAnalysisRequest(
                visual_case_id="visual-case-001",
                image_asset_ids=["image-001"],
            )
        )
        decision = evaluate_confirmation(
            result,
            professional(FindingSupport.SUPPORTS_FIRE, 0.88),
        )
        self.assertEqual(decision.status, VisualCaseStatus.CONFIRMED)

        handoff = build_confirmed_fire_handoff(
            visual_case(),
            decision,
            datetime(2026, 9, 9, 10, 31, tzinfo=UTC),
            confirmation_id="confirmation-001",
        )
        self.assertEqual(handoff.ignition_point.coordinates, (-121.37, 39.88))
        self.assertIn("image-001", handoff.evidence_ids)
        self.assertIn("detector-001", handoff.evidence_ids)

    async def test_model_only_support_is_uncertain(self) -> None:
        result = await SimulatedVisualProvider("confirmed").analyze(
            ImageAnalysisRequest(
                visual_case_id="visual-case-001",
                image_asset_ids=["image-001"],
            )
        )
        decision = evaluate_confirmation(
            result,
            professional(FindingSupport.UNAVAILABLE),
        )
        self.assertEqual(decision.status, VisualCaseStatus.UNCERTAIN)

    async def test_false_positive_agreement_rejects(self) -> None:
        result = await SimulatedVisualProvider("rejected").analyze(
            ImageAnalysisRequest(
                visual_case_id="visual-case-001",
                image_asset_ids=["image-001"],
            )
        )
        decision = evaluate_confirmation(
            result,
            professional(FindingSupport.AGAINST_FIRE, 0.95),
        )
        self.assertEqual(decision.status, VisualCaseStatus.REJECTED)

    async def test_poor_imagery_cannot_confirm(self) -> None:
        result = await SimulatedVisualProvider("poor_quality").analyze(
            ImageAnalysisRequest(
                visual_case_id="visual-case-001",
                image_asset_ids=["image-001"],
            )
        )
        decision = evaluate_confirmation(
            result,
            professional(FindingSupport.SUPPORTS_FIRE, 0.9),
        )
        self.assertEqual(decision.status, VisualCaseStatus.UNCERTAIN)

    async def test_non_confirmed_decision_cannot_be_handed_off(self) -> None:
        result = await SimulatedVisualProvider("uncertain").analyze(
            ImageAnalysisRequest(
                visual_case_id="visual-case-001",
                image_asset_ids=["image-001"],
            )
        )
        decision = evaluate_confirmation(
            result,
            professional(FindingSupport.UNAVAILABLE),
        )
        with self.assertRaises(ValueError):
            build_confirmed_fire_handoff(
                visual_case(),
                decision,
                datetime.now(UTC),
            )
