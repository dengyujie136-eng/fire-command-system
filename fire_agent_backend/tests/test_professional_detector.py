import unittest
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.visual_verification.models import (
    FireConfirmationRecord,
    VisualAnalysisRunRecord,
    VisualFindingRecord,
    VisualVerificationCaseRecord,
)
from app.visual_verification.professional_detector import persist_professional_detection
from app.visual_verification.review_service import (
    mark_case_analyzing,
    persist_review_decision,
    review_decision,
)
from app.visual_verification.schemas import (
    ConfirmationDecision,
    FindingSupport,
    ImageQuality,
    ProfessionalDetection,
    ProfessionalDetectionStartRequest,
    SceneType,
    VisualAnalysisFailure,
    VisualAnalysisResult,
    VisualDecision,
    VisualReviewStartRequest,
)
from app.visual_verification.states import VisualCaseStatus


MODEL_SHA256 = "fe2bdd32dc92c06ef2006e87718b6cbec9a4537a01cff79cf445737c83ee4fd7"


class ProfessionalDetectorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def asyncTearDown(self) -> None:
        await self.engine.dispose()

    @staticmethod
    def case() -> VisualVerificationCaseRecord:
        return VisualVerificationCaseRecord(
            visual_case_id="case-professional-001",
            source_candidate_id="candidate-001",
            upstream_schema_version="fire.hotspot.candidate.v0.1",
            upstream_status="candidate",
            event_id="event-001",
            event_name="Detector test",
            observed_at=datetime.now(UTC),
            longitude=-121.4,
            latitude=39.8,
            imagery_status="available",
            data_owner={"organization": "test"},
            replay_metadata={"is_replay": True},
            product_fields={},
            upstream_payload_hash="a" * 64,
            status="imagery_ready",
            version=1,
            is_simulated=True,
        )

    async def test_persists_fire_box_as_independent_evidence(self) -> None:
        async with self.sessions() as session:
            session.add(self.case())
            await session.flush()
            result = await persist_professional_detection(
                session,
                visual_case_id="case-professional-001",
                derivative_ids=["derivative-uav"],
                payload={
                    "model_name": "wildfire-detection-yolov8m",
                    "model_version": "ultralytics-8.4.39-yolov8m",
                    "model_sha256": MODEL_SHA256,
                    "confidence_threshold": 0.25,
                    "image_size": 640,
                    "duration_ms": 450,
                    "detections": [{
                        "image_id": "derivative-uav",
                        "class_id": 1,
                        "class_name": "fire",
                        "confidence": 0.688766,
                        "bbox_xyxy": [62.77, 21.81, 136.26, 84.87],
                    }],
                },
                is_simulated=True,
            )
            await session.commit()

            self.assertEqual(result.professional.support, FindingSupport.SUPPORTS_FIRE)
            self.assertEqual(result.professional.confidence, 0.688766)
            self.assertEqual(len(result.detections), 1)
            self.assertEqual(
                await session.scalar(select(func.count(VisualAnalysisRunRecord.id))), 1
            )
            self.assertEqual(
                await session.scalar(select(func.count(VisualFindingRecord.id))), 1
            )

    async def test_no_boxes_is_recorded_as_threshold_limited_negative_evidence(self) -> None:
        async with self.sessions() as session:
            session.add(self.case())
            await session.flush()
            result = await persist_professional_detection(
                session,
                visual_case_id="case-professional-001",
                derivative_ids=["derivative-clear"],
                payload={
                    "model_name": "wildfire-detection-yolov8m",
                    "model_version": "ultralytics-8.4.39-yolov8m",
                    "model_sha256": MODEL_SHA256,
                    "confidence_threshold": 0.25,
                    "image_size": 640,
                    "duration_ms": 400,
                    "detections": [],
                },
                is_simulated=False,
            )
            self.assertEqual(result.professional.support, FindingSupport.AGAINST_FIRE)
            self.assertEqual(result.professional.confidence, 0.75)
            self.assertIn("threshold", result.professional.summary)

    def test_request_rejects_duplicate_derivatives(self) -> None:
        with self.assertRaises(ValueError):
            ProfessionalDetectionStartRequest(
                derivative_ids=["same", "same"], confidence_threshold=0.25
            )

    def test_review_request_rejects_duplicate_derivatives(self) -> None:
        with self.assertRaises(ValueError):
            VisualReviewStartRequest(derivative_ids=["same", "same"])

    def test_review_confirms_only_when_qwen_and_detector_agree(self) -> None:
        visual = VisualAnalysisResult(
            analysis_run_id="run-qwen-001",
            visual_case_id="case-professional-001",
            fire_detected=True,
            flame_detected=True,
            smoke_detected=True,
            burn_scar_detected=False,
            wildfire_likelihood=0.92,
            image_quality=ImageQuality.GOOD,
            scene_type=SceneType.FOREST_WILDFIRE,
            decision=VisualDecision.CONFIRMED,
            reasoning_summary="Visible flame and smoke plume.",
            used_evidence_ids=["derivative-uav"],
            model_name="qwen-vl-max",
            model_version="qwen-vl-max",
            prompt_version="qwen-fire-v1",
        )
        professional = ProfessionalDetection(
            support=FindingSupport.SUPPORTS_FIRE,
            confidence=0.68,
            evidence_ids=["det-fire-001"],
            summary="Fire box detected.",
        )

        decision = review_decision(visual, professional)

        self.assertEqual(decision.status, VisualCaseStatus.CONFIRMED)
        self.assertEqual(decision.evidence_ids, ["derivative-uav", "det-fire-001"])

    def test_qwen_failure_cannot_be_promoted_by_detector(self) -> None:
        visual = VisualAnalysisFailure(
            analysis_run_id="run-qwen-failed",
            visual_case_id="case-professional-001",
            run_status="provider_error",
            error_code="provider_unavailable",
            error_message="Provider unavailable.",
            retryable=True,
            attempted_model_name="qwen-vl-max",
            attempted_model_version="qwen-vl-max",
            prompt_version="qwen-fire-v1",
            used_evidence_ids=["derivative-uav"],
        )
        professional = ProfessionalDetection(
            support=FindingSupport.SUPPORTS_FIRE,
            confidence=0.9,
            evidence_ids=["det-fire-001"],
            summary="Fire box detected.",
        )

        decision = review_decision(visual, professional)

        self.assertEqual(decision.status, VisualCaseStatus.FAILED)

    def test_course_demo_records_qwen_but_auto_confirms_screened_candidate(self) -> None:
        visual = VisualAnalysisResult(
            analysis_run_id="run-qwen-course-demo",
            visual_case_id="case-professional-001",
            fire_detected=False,
            flame_detected=False,
            smoke_detected=False,
            burn_scar_detected=False,
            wildfire_likelihood=0.0,
            image_quality=ImageQuality.USABLE,
            scene_type=SceneType.UNKNOWN,
            decision=VisualDecision.REJECTED,
            reasoning_summary="No visible flame or smoke in this optical crop.",
            used_evidence_ids=["derivative-dixie-rgb"],
            model_name="qwen3-vl-plus",
            model_version="qwen3-vl-plus",
            prompt_version="qwen-fire-v1",
        )
        professional = ProfessionalDetection(
            support=FindingSupport.AGAINST_FIRE,
            confidence=0.6,
            evidence_ids=["detector-dixie-001"],
            summary="No boxes above the detector threshold.",
        )

        decision = review_decision(
            visual,
            professional,
            assume_screened_candidate_is_fire=True,
            minimum_confirmation_confidence=0.70,
        )

        self.assertEqual(decision.status, VisualCaseStatus.CONFIRMED)
        self.assertEqual(decision.confidence, 0.70)
        self.assertIn("screened_candidate_assumed_true_for_course_demo", decision.reason_codes)
        self.assertIn("qwen_visual_rejected", decision.reason_codes)
        self.assertEqual(
            decision.evidence_ids,
            ["derivative-dixie-rgb", "detector-dixie-001"],
        )

    async def test_course_demo_confirmation_method_is_explicit(self) -> None:
        async with self.sessions() as session:
            case = self.case()
            session.add(case)
            await session.flush()
            await mark_case_analyzing(session, case)
            decision = ConfirmationDecision(
                status=VisualCaseStatus.CONFIRMED,
                confidence=0.7,
                reason_codes=[
                    "screened_candidate_assumed_true_for_course_demo",
                    "qwen_visual_rejected",
                ],
                evidence_ids=["derivative-dixie-rgb"],
            )

            record = await persist_review_decision(
                session,
                case=case,
                decision=decision,
                is_simulated=False,
            )
            await session.commit()

            self.assertEqual(record.status, VisualCaseStatus.CONFIRMED.value)
            self.assertEqual(record.confirmation_method, "course_demo_qwen_assisted_v1")
            self.assertEqual(record.rule_version, "course-demo-qwen-assisted-v1")
            self.assertFalse(record.is_simulated)

    async def test_persists_review_confirmation_and_terminal_case_state(self) -> None:
        async with self.sessions() as session:
            case = self.case()
            session.add(case)
            await session.flush()
            await mark_case_analyzing(session, case)
            decision = review_decision(
                VisualAnalysisResult(
                    analysis_run_id="run-qwen-002",
                    visual_case_id=case.visual_case_id,
                    fire_detected=True,
                    flame_detected=True,
                    smoke_detected=False,
                    burn_scar_detected=False,
                    wildfire_likelihood=0.9,
                    image_quality=ImageQuality.GOOD,
                    scene_type=SceneType.FOREST_WILDFIRE,
                    decision=VisualDecision.CONFIRMED,
                    reasoning_summary="Visible flame.",
                    used_evidence_ids=["derivative-uav"],
                    model_name="qwen-vl-max",
                    model_version="qwen-vl-max",
                    prompt_version="qwen-fire-v1",
                ),
                ProfessionalDetection(
                    support=FindingSupport.SUPPORTS_FIRE,
                    confidence=0.7,
                    evidence_ids=["det-fire-002"],
                ),
            )

            record = await persist_review_decision(
                session,
                case=case,
                decision=decision,
                is_simulated=True,
            )
            await session.commit()

            self.assertEqual(case.status, VisualCaseStatus.CONFIRMED.value)
            self.assertEqual(record.status, VisualCaseStatus.CONFIRMED.value)
            self.assertTrue(record.is_simulated)
            self.assertEqual(
                await session.scalar(select(func.count(FireConfirmationRecord.id))), 1
            )
