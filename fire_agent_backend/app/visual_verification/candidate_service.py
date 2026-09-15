from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.visual_verification.member_a_adapter import build_visual_case_id
from app.visual_verification.imagery_catalog_service import register_catalog_and_matches
from app.visual_verification.models import (
    VisualCaseAssetRecord,
    VisualVerificationCaseRecord,
)
from app.visual_verification.schemas import (
    CandidateIngestAction,
    CandidateIngestBatchResult,
    CandidateIngestItem,
    HotspotCandidate,
    HotspotCandidateEnvelope,
    UpstreamImageryStatus,
    VisualCaseRead,
)


class CandidateConflictError(ValueError):
    """The stable candidate ID was reused with changed immutable identity fields."""


def candidate_payload_hash(candidate: HotspotCandidate) -> str:
    payload = candidate.model_dump(mode="json")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _assert_immutable_identity(
    existing: VisualVerificationCaseRecord,
    candidate: HotspotCandidate,
) -> None:
    conflicts: list[str] = []
    if existing.event_id != candidate.event_id:
        conflicts.append("event_id")
    if existing.longitude != candidate.location.longitude:
        conflicts.append("longitude")
    if existing.latitude != candidate.location.latitude:
        conflicts.append("latitude")
    if _as_utc(existing.observed_at) != _as_utc(candidate.observed_at):
        conflicts.append("observed_at")
    if existing.is_simulated != candidate.is_simulated:
        conflicts.append("is_simulated")
    if existing.replay_metadata.get("is_replay") != candidate.replay.is_replay:
        conflicts.append("replay.is_replay")
    if conflicts:
        raise CandidateConflictError(
            f"candidate_id {candidate.candidate_id!r} changed immutable fields: "
            + ", ".join(conflicts)
        )


def _initial_visual_status(imagery_status: UpstreamImageryStatus) -> str:
    return {
        UpstreamImageryStatus.PENDING: "imagery_searching",
        UpstreamImageryStatus.AVAILABLE: "imagery_ready",
        UpstreamImageryStatus.UNAVAILABLE: "failed",
    }[imagery_status]


def _new_case_record(
    candidate: HotspotCandidate,
    *,
    version: int,
    payload_hash: str,
) -> VisualVerificationCaseRecord:
    return VisualVerificationCaseRecord(
        visual_case_id=build_visual_case_id(candidate.candidate_id, version),
        source_candidate_id=candidate.candidate_id,
        upstream_schema_version=candidate.schema_version,
        upstream_status=candidate.status.value,
        event_id=candidate.event_id,
        event_name=candidate.event_name,
        observation_id=None,
        observed_at=candidate.observed_at,
        longitude=candidate.location.longitude,
        latitude=candidate.location.latitude,
        source_cluster_id=candidate.source_cluster_id,
        cluster_point_count=candidate.cluster_point_count,
        cluster_mean_confidence=candidate.cluster_mean_confidence,
        cluster_max_frp_mw=candidate.cluster_max_frp_mw,
        imagery_status=candidate.imagery_status.value,
        data_owner=candidate.data_owner.model_dump(mode="json"),
        replay_metadata=candidate.replay.model_dump(mode="json"),
        product_fields=candidate.product_fields,
        upstream_payload_hash=payload_hash,
        status=_initial_visual_status(candidate.imagery_status),
        version=version,
        is_simulated=candidate.is_simulated,
    )


def _new_asset_records(
    candidate: HotspotCandidate,
    visual_case_id: str,
) -> list[VisualCaseAssetRecord]:
    records: list[VisualCaseAssetRecord] = []
    for index, reference in enumerate(candidate.imagery_refs):
        role = {
            "pre": "comparison_pre",
            "during": "primary",
            "post": "comparison_post",
            "context": "primary" if index == 0 else "context",
        }[reference.analysis_phase.value]
        records.append(
            VisualCaseAssetRecord(
                visual_case_id=visual_case_id,
                source_asset_id=reference.asset_id,
                asset_role=role,
                source_type="upstream_imagery_reference",
                source_name=reference.source,
                mime_type=reference.mime_type,
                acquired_at=reference.acquired_at,
                content_uri=reference.uri,
                quality_status=(reference.quality_status.value if reference.quality_status else "unassessed"),
                checksum_sha256=reference.checksum_sha256,
                is_simulated=candidate.is_simulated,
            )
        )
    return records


async def _asset_count(db: AsyncSession, visual_case_id: str) -> int:
    result = await db.execute(
        select(func.count(VisualCaseAssetRecord.id)).where(
            VisualCaseAssetRecord.visual_case_id == visual_case_id
        )
    )
    return int(result.scalar_one())


async def ingest_candidate(
    db: AsyncSession,
    candidate: HotspotCandidate,
) -> CandidateIngestItem:
    result = await db.execute(
        select(VisualVerificationCaseRecord)
        .where(
            VisualVerificationCaseRecord.event_id == candidate.event_id,
            VisualVerificationCaseRecord.source_candidate_id == candidate.candidate_id,
        )
        .order_by(desc(VisualVerificationCaseRecord.version))
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    payload_hash = candidate_payload_hash(candidate)

    if latest is not None and latest.upstream_payload_hash == payload_hash:
        return CandidateIngestItem(
            action=CandidateIngestAction.DUPLICATE,
            case=VisualCaseRead.model_validate(latest),
            asset_count=await _asset_count(db, latest.visual_case_id),
        )

    if latest is not None:
        _assert_immutable_identity(latest, candidate)
    version = 1 if latest is None else latest.version + 1
    record = _new_case_record(candidate, version=version, payload_hash=payload_hash)
    db.add(record)
    await db.flush()
    assets = _new_asset_records(candidate, record.visual_case_id)
    db.add_all(assets)
    await db.flush()
    await register_catalog_and_matches(
        db,
        candidate=candidate,
        visual_case_id=record.visual_case_id,
    )

    return CandidateIngestItem(
        action=(
            CandidateIngestAction.CREATED
            if latest is None
            else CandidateIngestAction.VERSIONED
        ),
        case=VisualCaseRead.model_validate(record),
        asset_count=len(assets),
    )


async def ingest_candidate_envelope(
    db: AsyncSession,
    envelope: HotspotCandidateEnvelope,
) -> CandidateIngestBatchResult:
    items = [await ingest_candidate(db, candidate) for candidate in envelope.candidates]
    return CandidateIngestBatchResult(
        event_id=envelope.event_id,
        generated_at=envelope.generated_at,
        items=items,
    )


async def list_visual_cases(
    db: AsyncSession,
    *,
    event_id: str | None = None,
    visual_status: str | None = None,
    upstream_status: str | None = None,
    imagery_status: str | None = None,
    include_history: bool = False,
    limit: int = 100,
) -> list[VisualVerificationCaseRecord]:
    statement = select(VisualVerificationCaseRecord)
    if not include_history:
        latest_versions = (
            select(
                VisualVerificationCaseRecord.event_id.label("event_id"),
                VisualVerificationCaseRecord.source_candidate_id.label("source_candidate_id"),
                func.max(VisualVerificationCaseRecord.version).label("max_version"),
            )
            .group_by(
                VisualVerificationCaseRecord.event_id,
                VisualVerificationCaseRecord.source_candidate_id,
            )
            .subquery()
        )
        statement = statement.join(
            latest_versions,
            (VisualVerificationCaseRecord.event_id == latest_versions.c.event_id)
            & (
                VisualVerificationCaseRecord.source_candidate_id
                == latest_versions.c.source_candidate_id
            )
            & (VisualVerificationCaseRecord.version == latest_versions.c.max_version),
        )
    if event_id is not None:
        statement = statement.where(VisualVerificationCaseRecord.event_id == event_id)
    if visual_status is not None:
        statement = statement.where(VisualVerificationCaseRecord.status == visual_status)
    if upstream_status is not None:
        statement = statement.where(
            VisualVerificationCaseRecord.upstream_status == upstream_status
        )
    if imagery_status is not None:
        statement = statement.where(
            VisualVerificationCaseRecord.imagery_status == imagery_status
        )
    result = await db.execute(
        statement.order_by(
            desc(VisualVerificationCaseRecord.observed_at),
            desc(VisualVerificationCaseRecord.version),
        ).limit(max(1, min(limit, 500)))
    )
    return list(result.scalars().all())


async def list_candidate_history(
    db: AsyncSession,
    *,
    event_id: str,
    source_candidate_id: str,
) -> list[VisualVerificationCaseRecord]:
    result = await db.execute(
        select(VisualVerificationCaseRecord)
        .where(
            VisualVerificationCaseRecord.event_id == event_id,
            VisualVerificationCaseRecord.source_candidate_id == source_candidate_id,
        )
        .order_by(VisualVerificationCaseRecord.version)
    )
    return list(result.scalars().all())


async def get_visual_case(
    db: AsyncSession,
    visual_case_id: str,
) -> VisualVerificationCaseRecord | None:
    result = await db.execute(
        select(VisualVerificationCaseRecord).where(
            VisualVerificationCaseRecord.visual_case_id == visual_case_id
        )
    )
    return result.scalar_one_or_none()


async def list_case_assets(
    db: AsyncSession,
    visual_case_id: str,
) -> list[VisualCaseAssetRecord]:
    result = await db.execute(
        select(VisualCaseAssetRecord)
        .where(VisualCaseAssetRecord.visual_case_id == visual_case_id)
        .order_by(VisualCaseAssetRecord.id)
    )
    return list(result.scalars().all())
