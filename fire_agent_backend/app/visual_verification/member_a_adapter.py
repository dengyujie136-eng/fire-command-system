from __future__ import annotations

import hashlib

from app.visual_verification.schemas import (
    HotspotCandidate,
    HotspotCandidateEnvelope,
    VisualCase,
)
from app.visual_verification.states import VisualCaseStatus


def build_visual_case_id(candidate_id: str, version: int = 1) -> str:
    """Build a bounded internal identifier without altering member A's stable ID."""

    digest = hashlib.sha256(candidate_id.encode("utf-8")).hexdigest()[:24]
    return f"visual-case-{digest}-v{version}"


def adapt_hotspot_candidate(candidate: HotspotCandidate, version: int = 1) -> VisualCase:
    """Translate the A-to-B transport DTO into B's stable internal case model."""

    return VisualCase(
        visual_case_id=build_visual_case_id(candidate.candidate_id, version),
        source_candidate_id=candidate.candidate_id,
        event_id=candidate.event_id,
        observed_at=candidate.observed_at,
        longitude=candidate.location.longitude,
        latitude=candidate.location.latitude,
        source_asset_ids=[reference.asset_id for reference in candidate.imagery_refs],
        status=VisualCaseStatus.RECEIVED,
        is_simulated=candidate.is_simulated,
        version=version,
    )


def adapt_hotspot_envelope(envelope: HotspotCandidateEnvelope) -> list[VisualCase]:
    """Adapt one HTTP/MQTT batch while preserving its order."""

    return [adapt_hotspot_candidate(candidate) for candidate in envelope.candidates]
