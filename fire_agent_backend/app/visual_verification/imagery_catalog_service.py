from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.visual_verification.models import (
    CandidateImageryMatchRecord,
    ImageryAssetCatalogRecord,
)
from app.visual_verification.schemas import HotspotCandidate, HotspotImageryReference


def _bounded(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


def _temporal_score(candidate: HotspotCandidate, reference: HotspotImageryReference) -> float:
    observed = candidate.observed_at.astimezone(UTC)
    if reference.acquired_at is not None:
        days = abs((reference.acquired_at.astimezone(UTC) - observed).total_seconds()) / 86400
        return _bounded(1.0 - days / 30.0)
    if reference.time_start is not None and reference.time_end is not None:
        start = reference.time_start.astimezone(UTC)
        end = reference.time_end.astimezone(UTC)
        if start <= observed <= end:
            return 1.0
        distance = min(abs((observed - start).total_seconds()), abs((observed - end).total_seconds()))
        return _bounded(1.0 - distance / (30 * 86400))
    return 0.5


def _footprint_bbox(geojson: dict[str, object] | None) -> tuple[float, float, float, float] | None:
    if not geojson:
        return None
    coordinates = geojson.get("coordinates")
    numbers: list[tuple[float, float]] = []

    def visit(value: object) -> None:
        if isinstance(value, (list, tuple)):
            if len(value) >= 2 and all(isinstance(item, (int, float)) for item in value[:2]):
                numbers.append((float(value[0]), float(value[1])))
            else:
                for item in value:
                    visit(item)

    visit(coordinates)
    if not numbers:
        return None
    xs, ys = zip(*numbers)
    return min(xs), min(ys), max(xs), max(ys)


def _spatial_score(candidate: HotspotCandidate, reference: HotspotImageryReference) -> float:
    bbox = _footprint_bbox(reference.footprint_geojson)
    if bbox is None:
        return 0.8  # Explicit upstream linkage, but no machine-verifiable footprint.
    west, south, east, north = bbox
    return 1.0 if west <= candidate.location.longitude <= east and south <= candidate.location.latitude <= north else 0.0


def _resolution_score(resolution_m: float | None) -> float:
    if resolution_m is None:
        return 0.5
    if resolution_m <= 10:
        return 1.0
    if resolution_m <= 20:
        return 0.85
    if resolution_m <= 30:
        return 0.7
    return _bounded(30.0 / resolution_m)


def _match_scores(candidate: HotspotCandidate, reference: HotspotImageryReference) -> dict[str, float]:
    spatial = _spatial_score(candidate, reference)
    temporal = _temporal_score(candidate, reference)
    cloud = 0.6 if reference.cloud_cover is None else _bounded(1 - reference.cloud_cover / 100)
    valid = 0.7 if reference.valid_pixel_ratio is None else reference.valid_pixel_ratio
    resolution = _resolution_score(reference.resolution_m)
    total = 0.35 * spatial + 0.30 * temporal + 0.15 * cloud + 0.10 * valid + 0.10 * resolution
    return {
        "spatial_score": _bounded(spatial),
        "temporal_score": _bounded(temporal),
        "cloud_score": _bounded(cloud),
        "valid_pixel_score": _bounded(valid),
        "resolution_score": _bounded(resolution),
        "matching_score": _bounded(total),
    }


async def register_catalog_and_matches(
    db: AsyncSession,
    *,
    candidate: HotspotCandidate,
    visual_case_id: str,
) -> None:
    for reference in candidate.imagery_refs:
        catalog = await db.scalar(
            select(ImageryAssetCatalogRecord).where(
                ImageryAssetCatalogRecord.asset_id == reference.asset_id
            )
        )
        if catalog is None:
            catalog = ImageryAssetCatalogRecord(
                asset_id=reference.asset_id,
                event_id=candidate.event_id,
                source_name=reference.source,
                source_type="upstream_imagery_reference",
                analysis_phase=reference.analysis_phase.value,
                mime_type=reference.mime_type,
                time_start=reference.time_start or reference.acquired_at,
                time_end=reference.time_end or reference.acquired_at,
                content_uri=reference.uri,
                footprint_geojson=reference.footprint_geojson,
                crs=reference.crs,
                resolution_m=reference.resolution_m,
                bands=reference.bands,
                cloud_cover=reference.cloud_cover,
                valid_pixel_ratio=reference.valid_pixel_ratio,
                quality_status=(reference.quality_status.value if reference.quality_status else "unassessed"),
                checksum_sha256=reference.checksum_sha256,
                metadata_json={},
                is_simulated=candidate.is_simulated,
            )
            db.add(catalog)
            await db.flush()
        elif catalog.event_id != candidate.event_id or catalog.content_uri != reference.uri:
            raise ValueError(f"asset_id {reference.asset_id!r} conflicts with imagery catalog")

        digest = hashlib.sha256(f"{visual_case_id}:{reference.asset_id}".encode()).hexdigest()[:28]
        existing = await db.scalar(
            select(CandidateImageryMatchRecord).where(
                CandidateImageryMatchRecord.visual_case_id == visual_case_id,
                CandidateImageryMatchRecord.asset_id == reference.asset_id,
            )
        )
        if existing is not None:
            continue
        scores = _match_scores(candidate, reference)
        reasons = [
            f"phase:{reference.analysis_phase.value}",
            "explicit_upstream_reference",
            "spatially_covered" if scores["spatial_score"] == 1 else "spatial_coverage_unverified",
            "temporally_matched" if scores["temporal_score"] >= 0.8 else "temporal_match_limited",
        ]
        db.add(
            CandidateImageryMatchRecord(
                match_id=f"cim_{digest}",
                visual_case_id=visual_case_id,
                asset_id=reference.asset_id,
                match_reason=reasons,
                is_selected=scores["spatial_score"] > 0,
                **scores,
            )
        )
    await db.flush()


async def list_catalog_assets(db: AsyncSession, *, event_id: str) -> list[ImageryAssetCatalogRecord]:
    result = await db.execute(
        select(ImageryAssetCatalogRecord)
        .where(ImageryAssetCatalogRecord.event_id == event_id)
        .order_by(ImageryAssetCatalogRecord.time_start, ImageryAssetCatalogRecord.asset_id)
    )
    return list(result.scalars().all())


async def list_candidate_matches(db: AsyncSession, *, visual_case_id: str) -> list[CandidateImageryMatchRecord]:
    result = await db.execute(
        select(CandidateImageryMatchRecord)
        .where(CandidateImageryMatchRecord.visual_case_id == visual_case_id)
        .order_by(CandidateImageryMatchRecord.matching_score.desc())
    )
    return list(result.scalars().all())

