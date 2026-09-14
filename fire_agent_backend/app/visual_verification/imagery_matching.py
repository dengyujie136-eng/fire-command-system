from __future__ import annotations

from datetime import timedelta

from app.visual_verification.schemas import (
    HotspotCandidate,
    ImageryAssetReference,
    ImageryMatchResult,
    ImageryMatchStatus,
    ImageQuality,
    UpstreamImageryStatus,
)


QUALITY_SCORE = {
    ImageQuality.GOOD: 1.0,
    ImageQuality.USABLE: 0.75,
    ImageQuality.POOR: 0.25,
    ImageQuality.INVALID: 0.0,
}
ROLE_SCORE = {"primary": 1.0, "context": 0.8, "comparison": 0.7}


def _asset_score(
    candidate: HotspotCandidate,
    asset: ImageryAssetReference,
    max_time_delta: timedelta,
) -> tuple[float, list[str]]:
    reference = next(item for item in candidate.imagery_refs if item.asset_id == asset.asset_id)
    delta_seconds = abs((reference.acquired_at - candidate.observed_at).total_seconds())
    allowed_seconds = max(max_time_delta.total_seconds(), 1)
    temporal_score = max(0.0, 1.0 - delta_seconds / allowed_seconds)
    score = (
        0.55 * QUALITY_SCORE[asset.quality]
        + 0.30 * temporal_score
        + 0.15 * ROLE_SCORE[asset.role]
    )
    warnings: list[str] = []
    if delta_seconds > allowed_seconds:
        warnings.append(f"ASSET_OUTSIDE_TIME_WINDOW:{asset.asset_id}")
    if asset.quality == ImageQuality.POOR:
        warnings.append(f"LOW_QUALITY_ASSET:{asset.asset_id}")
    return round(score, 4), warnings


def match_candidate_imagery(
    candidate: HotspotCandidate,
    inventory: list[ImageryAssetReference],
    *,
    max_time_delta: timedelta = timedelta(days=7),
) -> ImageryMatchResult:
    """Match explicit A-side references to B-side assets without using hidden truth."""

    if candidate.imagery_status == UpstreamImageryStatus.PENDING:
        return ImageryMatchResult(
            candidate_id=candidate.candidate_id,
            match_status=ImageryMatchStatus.PENDING,
            matching_score=0,
            warnings=["IMAGERY_PENDING"],
            is_simulated=candidate.is_simulated,
        )
    if candidate.imagery_status == UpstreamImageryStatus.UNAVAILABLE:
        return ImageryMatchResult(
            candidate_id=candidate.candidate_id,
            match_status=ImageryMatchStatus.UNAVAILABLE,
            matching_score=0,
            warnings=["NO_IMAGERY_AVAILABLE"],
            is_simulated=candidate.is_simulated,
        )

    inventory_by_id = {asset.asset_id: asset for asset in inventory}
    selected: list[ImageryAssetReference] = []
    rejected_ids: list[str] = []
    warnings: list[str] = []
    scores: list[float] = []

    for reference in candidate.imagery_refs:
        asset = inventory_by_id.get(reference.asset_id)
        if asset is None:
            rejected_ids.append(reference.asset_id)
            warnings.append(f"ASSET_NOT_REGISTERED:{reference.asset_id}")
            continue
        if asset.candidate_id != candidate.candidate_id:
            rejected_ids.append(reference.asset_id)
            warnings.append(f"ASSET_CANDIDATE_MISMATCH:{reference.asset_id}")
            continue
        if asset.coverage_bbox is not None:
            west, south, east, north = asset.coverage_bbox
            if not (
                west <= candidate.location.longitude <= east
                and south <= candidate.location.latitude <= north
            ):
                rejected_ids.append(reference.asset_id)
                warnings.append(f"ASSET_OUTSIDE_SPATIAL_COVERAGE:{reference.asset_id}")
                continue
        if asset.quality == ImageQuality.INVALID:
            rejected_ids.append(reference.asset_id)
            warnings.append(f"INVALID_ASSET:{reference.asset_id}")
            continue
        selected.append(asset)
        score, asset_warnings = _asset_score(candidate, asset, max_time_delta)
        scores.append(score)
        warnings.extend(asset_warnings)

    if not selected:
        return ImageryMatchResult(
            candidate_id=candidate.candidate_id,
            match_status=ImageryMatchStatus.INVALID_REFERENCE,
            rejected_asset_ids=rejected_ids,
            matching_score=0,
            warnings=warnings or ["NO_VALID_REFERENCED_ASSET"],
            is_simulated=candidate.is_simulated,
        )

    by_role = {
        role: [asset.asset_id for asset in selected if asset.role == role]
        for role in ("primary", "context", "comparison")
    }
    partial = bool(rejected_ids or warnings or not by_role["primary"])
    return ImageryMatchResult(
        candidate_id=candidate.candidate_id,
        match_status=(
            ImageryMatchStatus.PARTIALLY_MATCHED if partial else ImageryMatchStatus.MATCHED
        ),
        primary_asset_ids=by_role["primary"],
        context_asset_ids=by_role["context"],
        comparison_asset_ids=by_role["comparison"],
        rejected_asset_ids=rejected_ids,
        matching_score=round(sum(scores) / len(scores), 4),
        warnings=list(dict.fromkeys(warnings)),
        is_simulated=candidate.is_simulated,
    )
