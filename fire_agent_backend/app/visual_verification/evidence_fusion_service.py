from __future__ import annotations

from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.visual_verification.models import (
    CandidateImageryMatchRecord,
    EvidenceFusionRunRecord,
    VisualVerificationCaseRecord,
)
from app.visual_verification.schemas import (
    FindingSupport,
    ImageQuality,
    ProfessionalDetection,
    VisualAnalysisFailure,
    VisualAnalysisResult,
)


FUSION_RULE_VERSION = "multi-evidence-fusion-v1"
FUSION_WEIGHTS = {
    "thermal": 0.30,
    "cluster": 0.20,
    "qwen_visual": 0.20,
    "detector": 0.10,
    "temporal_change": 0.10,
    "imagery_quality": 0.10,
}


def _bounded(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


def _number(fields: dict, *names: str) -> float | None:
    sources = [fields]
    for nested_name in ("firms", "thermal", "source"):
        nested = fields.get(nested_name)
        if isinstance(nested, dict):
            sources.append(nested)
    for source in sources:
        for name in names:
            value = source.get(name)
            if value is not None and not isinstance(value, bool):
                try:
                    return float(value)
                except (TypeError, ValueError):
                    pass
    return None


def _thermal_score(case: VisualVerificationCaseRecord) -> float:
    confidence = _number(case.product_fields, "confidence_score") or 0.5
    frp = _number(case.product_fields, "frp_mw", "frp") or 0.0
    i4 = _number(case.product_fields, "brightness_ti4", "bright_ti4")
    i5 = _number(case.product_fields, "brightness_ti5", "bright_ti5")
    contrast = _bounded(((i4 - i5) / 80.0) if i4 is not None and i5 is not None else 0.5)
    return _bounded(0.45 * confidence + 0.35 * _bounded(frp / 20.0) + 0.20 * contrast)


def _cluster_score(case: VisualVerificationCaseRecord) -> float:
    confidence = case.cluster_mean_confidence
    if confidence is None:
        confidence = _number(case.product_fields, "confidence_score") or 0.5
    count = case.cluster_point_count or 1
    max_frp = case.cluster_max_frp_mw
    if max_frp is None:
        max_frp = _number(case.product_fields, "frp_mw", "frp") or 0.0
    return _bounded(0.45 * confidence + 0.30 * _bounded(count / 4.0) + 0.25 * _bounded(max_frp / 20.0))


async def persist_evidence_fusion(
    db: AsyncSession,
    *,
    case: VisualVerificationCaseRecord,
    visual: VisualAnalysisResult | VisualAnalysisFailure,
    professional: ProfessionalDetection,
) -> EvidenceFusionRunRecord:
    imagery_match = await db.scalar(
        select(func.avg(CandidateImageryMatchRecord.matching_score)).where(
            CandidateImageryMatchRecord.visual_case_id == case.visual_case_id,
            CandidateImageryMatchRecord.is_selected.is_(True),
        )
    )
    quality_score = {
        ImageQuality.GOOD: 1.0,
        ImageQuality.USABLE: 0.75,
        ImageQuality.POOR: 0.25,
        ImageQuality.INVALID: 0.0,
    }.get(visual.image_quality, 0.0) if isinstance(visual, VisualAnalysisResult) else 0.0
    imagery_quality = _bounded((float(imagery_match or 0.5) + quality_score) / 2)
    qwen_score = visual.wildfire_likelihood if isinstance(visual, VisualAnalysisResult) else 0.0
    detector_score = 0.0
    if professional.support == FindingSupport.SUPPORTS_FIRE:
        detector_score = professional.confidence or 0.0
    elif professional.support == FindingSupport.UNAVAILABLE:
        detector_score = 0.5
    change_score = _number(case.product_fields, "temporal_change_score", "change_score") or 0.5
    component_scores = {
        "thermal": _thermal_score(case),
        "cluster": _cluster_score(case),
        "qwen_visual": _bounded(qwen_score),
        "detector": _bounded(detector_score),
        "temporal_change": _bounded(change_score),
        "imagery_quality": imagery_quality,
    }
    final_score = _bounded(sum(component_scores[name] * weight for name, weight in FUSION_WEIGHTS.items()))
    visually_supported = (
        isinstance(visual, VisualAnalysisResult)
        and (visual.fire_detected or visual.flame_detected or visual.smoke_detected)
    ) or professional.support == FindingSupport.SUPPORTS_FIRE
    if final_score >= 0.75 and visually_supported:
        decision = "confirmed_strict"
    elif final_score >= 0.55 and component_scores["thermal"] >= 0.55:
        decision = "confirmed_thermal"
    elif final_score < 0.30 and not visually_supported:
        decision = "rejected"
    else:
        decision = "uncertain"
    evidence_ids = list(dict.fromkeys([
        *visual.used_evidence_ids,
        *professional.evidence_ids,
        case.source_candidate_id,
        *([case.source_cluster_id] if case.source_cluster_id else []),
    ]))
    record = EvidenceFusionRunRecord(
        fusion_run_id=f"fusion_{uuid4().hex}",
        visual_case_id=case.visual_case_id,
        component_scores=component_scores,
        weights=FUSION_WEIGHTS,
        final_score=final_score,
        decision=decision,
        rule_version=FUSION_RULE_VERSION,
        evidence_ids=evidence_ids,
    )
    db.add(record)
    await db.flush()
    return record


async def list_evidence_fusions(db: AsyncSession, *, visual_case_id: str) -> list[EvidenceFusionRunRecord]:
    result = await db.execute(
        select(EvidenceFusionRunRecord)
        .where(EvidenceFusionRunRecord.visual_case_id == visual_case_id)
        .order_by(EvidenceFusionRunRecord.created_at.desc())
    )
    return list(result.scalars().all())

