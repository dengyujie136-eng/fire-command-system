from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.visual_verification.confirmation_rules import evaluate_confirmation
from app.visual_verification.models import (
    FireConfirmationRecord,
    VisualVerificationCaseRecord,
)
from app.visual_verification.schemas import (
    ConfirmationDecision,
    ProfessionalDetection,
    VisualAnalysisFailure,
    VisualAnalysisResult,
)
from app.visual_verification.states import VisualCaseStatus, ensure_visual_case_transition


REVIEW_RULE_VERSION = "qwen-yolo-fusion-v1"
COURSE_DEMO_RULE_VERSION = "course-demo-qwen-assisted-v1"
COURSE_DEMO_AUTO_CONFIRM_REASON = "screened_candidate_assumed_true_for_course_demo"


def _unique_evidence_ids(
    visual: VisualAnalysisResult | VisualAnalysisFailure,
    professional: ProfessionalDetection,
) -> list[str]:
    ids = [*visual.used_evidence_ids, *professional.evidence_ids]
    if not ids:
        ids.append(visual.analysis_run_id)
    return list(dict.fromkeys(ids))


def review_decision(
    visual: VisualAnalysisResult | VisualAnalysisFailure,
    professional: ProfessionalDetection,
    *,
    assume_screened_candidate_is_fire: bool = False,
    minimum_confirmation_confidence: float = 0.70,
) -> ConfirmationDecision:
    if isinstance(visual, VisualAnalysisFailure):
        strict_decision = ConfirmationDecision(
            status=VisualCaseStatus.FAILED,
            confidence=0,
            reason_codes=[f"visual_{visual.run_status}", visual.error_code],
            evidence_ids=visual.used_evidence_ids,
        )
    else:
        strict_decision = evaluate_confirmation(visual, professional)

    if not assume_screened_candidate_is_fire or strict_decision.status == VisualCaseStatus.CONFIRMED:
        return strict_decision

    if isinstance(visual, VisualAnalysisFailure):
        qwen_reason = "qwen_visual_unavailable"
        qwen_confidence = 0.0
    else:
        qwen_reason = f"qwen_visual_{visual.decision.value}"
        qwen_confidence = visual.wildfire_likelihood

    detector_reason = f"professional_detector_{professional.support.value}"
    supporting_detector_confidence = (
        professional.confidence
        if professional.support.value == "supports_fire" and professional.confidence is not None
        else 0.0
    )
    confidence = round(
        max(minimum_confirmation_confidence, qwen_confidence, supporting_detector_confidence),
        4,
    )
    return ConfirmationDecision(
        status=VisualCaseStatus.CONFIRMED,
        confidence=confidence,
        reason_codes=[
            COURSE_DEMO_AUTO_CONFIRM_REASON,
            f"strict_visual_result_{strict_decision.status.value}",
            qwen_reason,
            detector_reason,
        ],
        evidence_ids=_unique_evidence_ids(visual, professional),
    )


async def mark_case_analyzing(
    db: AsyncSession,
    case: VisualVerificationCaseRecord,
) -> None:
    current = VisualCaseStatus(case.status)
    ensure_visual_case_transition(current, VisualCaseStatus.ANALYZING)
    case.status = VisualCaseStatus.ANALYZING.value
    await db.flush()


async def persist_review_decision(
    db: AsyncSession,
    *,
    case: VisualVerificationCaseRecord,
    decision: ConfirmationDecision,
    is_simulated: bool,
) -> FireConfirmationRecord:
    ensure_visual_case_transition(VisualCaseStatus(case.status), decision.status)
    await db.execute(
        update(FireConfirmationRecord)
        .where(
            FireConfirmationRecord.visual_case_id == case.visual_case_id,
            FireConfirmationRecord.is_current.is_(True),
        )
        .values(is_current=False)
    )
    latest_version = await db.scalar(
        select(func.max(FireConfirmationRecord.version)).where(
            FireConfirmationRecord.visual_case_id == case.visual_case_id
        )
    )
    now = datetime.now(UTC)
    course_demo_confirmation = COURSE_DEMO_AUTO_CONFIRM_REASON in decision.reason_codes
    record = FireConfirmationRecord(
        confirmation_id=f"vfc_{uuid4().hex}",
        visual_case_id=case.visual_case_id,
        source_candidate_id=case.source_candidate_id,
        version=(latest_version or 0) + 1,
        is_current=True,
        status=decision.status.value,
        confidence=decision.confidence,
        reason_codes=decision.reason_codes,
        evidence_ids=decision.evidence_ids,
        longitude=case.longitude if decision.status == VisualCaseStatus.CONFIRMED else None,
        latitude=case.latitude if decision.status == VisualCaseStatus.CONFIRMED else None,
        area_geojson=None,
        confirmation_method=(
            "course_demo_qwen_assisted_v1"
            if course_demo_confirmation
            else "qwen_yolo_fusion_v1"
        ),
        rule_version=(COURSE_DEMO_RULE_VERSION if course_demo_confirmation else REVIEW_RULE_VERSION),
        confirmed_at=now if decision.status == VisualCaseStatus.CONFIRMED else None,
        is_simulated=is_simulated,
    )
    db.add(record)
    case.status = decision.status.value
    await db.flush()
    return record
