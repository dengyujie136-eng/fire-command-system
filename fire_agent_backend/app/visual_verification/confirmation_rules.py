from datetime import datetime
from uuid import uuid4

from app.visual_verification.schemas import (
    ConfirmedFirePoint,
    ConfirmationDecision,
    FindingSupport,
    GeoJsonPoint,
    ImageQuality,
    ProfessionalDetection,
    SceneType,
    VisualAnalysisResult,
    VisualCase,
    VisualDecision,
)
from app.visual_verification.states import AnalysisRunStatus, VisualCaseStatus


FALSE_POSITIVE_SCENES = {
    SceneType.INDUSTRIAL_HEAT,
    SceneType.BARE_GROUND,
    SceneType.CLOUD_OR_FOG,
}


def _evidence_ids(
    visual: VisualAnalysisResult,
    professional: ProfessionalDetection,
) -> list[str]:
    return list(dict.fromkeys([*visual.used_evidence_ids, *professional.evidence_ids]))


def _combined_confidence(
    visual: VisualAnalysisResult,
    professional: ProfessionalDetection,
) -> float:
    if professional.confidence is None:
        return round(visual.wildfire_likelihood, 4)
    return round(visual.wildfire_likelihood * 0.55 + professional.confidence * 0.45, 4)


def evaluate_confirmation(
    visual: VisualAnalysisResult,
    professional: ProfessionalDetection,
) -> ConfirmationDecision:
    """Apply conservative, evidence-gated confirmation rules.

    A provider failure never enters this function as a successful fire decision.
    Poor/invalid imagery and cross-model disagreement cannot confirm or reject a
    candidate automatically.
    """

    evidence_ids = _evidence_ids(visual, professional)

    if visual.run_status != AnalysisRunStatus.SUCCEEDED:
        return ConfirmationDecision(
            status=VisualCaseStatus.FAILED,
            confidence=0,
            reason_codes=[f"visual_run_{visual.run_status.value}"],
            evidence_ids=evidence_ids,
        )

    if visual.image_quality == ImageQuality.INVALID:
        return ConfirmationDecision(
            status=VisualCaseStatus.FAILED,
            confidence=0,
            reason_codes=["invalid_imagery"],
            evidence_ids=evidence_ids,
        )

    if visual.image_quality == ImageQuality.POOR:
        return ConfirmationDecision(
            status=VisualCaseStatus.UNCERTAIN,
            confidence=visual.wildfire_likelihood,
            reason_codes=["poor_imagery_requires_more_evidence"],
            evidence_ids=evidence_ids,
        )

    if (
        visual.decision == VisualDecision.CONFIRMED
        and professional.support == FindingSupport.SUPPORTS_FIRE
    ):
        return ConfirmationDecision(
            status=VisualCaseStatus.CONFIRMED,
            confidence=_combined_confidence(visual, professional),
            reason_codes=["visual_and_professional_evidence_agree"],
            evidence_ids=evidence_ids,
        )

    if (
        visual.decision == VisualDecision.REJECTED
        and visual.scene_type in FALSE_POSITIVE_SCENES
        and professional.support == FindingSupport.AGAINST_FIRE
    ):
        return ConfirmationDecision(
            status=VisualCaseStatus.REJECTED,
            confidence=round(1 - _combined_confidence(visual, professional), 4),
            reason_codes=["independent_evidence_identifies_false_positive"],
            evidence_ids=evidence_ids,
        )

    reason_codes = ["insufficient_or_conflicting_evidence"]
    if professional.support == FindingSupport.UNAVAILABLE:
        reason_codes.append("professional_detection_unavailable")
    if visual.decision == VisualDecision.UNCERTAIN:
        reason_codes.append("visual_model_uncertain")

    return ConfirmationDecision(
        status=VisualCaseStatus.UNCERTAIN,
        confidence=_combined_confidence(visual, professional),
        reason_codes=reason_codes,
        evidence_ids=evidence_ids,
    )


def build_confirmed_fire_handoff(
    case: VisualCase,
    decision: ConfirmationDecision,
    confirmed_at: datetime,
    *,
    confirmation_id: str | None = None,
) -> ConfirmedFirePoint:
    if decision.status != VisualCaseStatus.CONFIRMED:
        raise ValueError("Only a confirmed visual case can be handed to the spread model")
    if confirmed_at.tzinfo is None or confirmed_at.utcoffset() is None:
        raise ValueError("confirmed_at must include a timezone")
    if not decision.evidence_ids:
        raise ValueError("A confirmed fire point must reference evidence")

    return ConfirmedFirePoint(
        confirmation_id=confirmation_id or f"vfc_{uuid4().hex}",
        event_id=case.event_id,
        source_candidate_id=case.source_candidate_id,
        confirmed_at=confirmed_at,
        ignition_point=GeoJsonPoint(coordinates=(case.longitude, case.latitude)),
        confidence=decision.confidence,
        evidence_ids=decision.evidence_ids,
        is_simulated=case.is_simulated,
    )
