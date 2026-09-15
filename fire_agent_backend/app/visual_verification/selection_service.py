from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.visual_verification.models import (
    FireConfirmationRecord,
    VisualVerificationCaseRecord,
)
from app.visual_verification.schemas import (
    ConfirmedFirePointRead,
    FirePointSelectionRequest,
    FirePointSelectionResult,
    GeoJsonPoint,
    SelectedFirePointCandidate,
)


EARTH_RADIUS_KM = 6371.0088


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _haversine_km(
    longitude_a: float,
    latitude_a: float,
    longitude_b: float,
    latitude_b: float,
) -> float:
    lat_a, lat_b = math.radians(latitude_a), math.radians(latitude_b)
    delta_lat = lat_b - lat_a
    delta_lon = math.radians(longitude_b - longitude_a)
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(value))


def _number(product_fields: dict[str, Any], *names: str) -> float | None:
    sources = [product_fields]
    for nested_name in ("firms", "thermal", "source"):
        nested = product_fields.get(nested_name)
        if isinstance(nested, dict):
            sources.append(nested)
    for source in sources:
        for name in names:
            value = source.get(name)
            if value is None or isinstance(value, bool):
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None


@dataclass
class _Cluster:
    source_cluster_id: str | None = None
    members: list[VisualVerificationCaseRecord] = field(default_factory=list)
    longitude_sum: float = 0.0
    latitude_sum: float = 0.0
    start_at: datetime | None = None
    end_at: datetime | None = None

    @property
    def longitude(self) -> float:
        return self.longitude_sum / len(self.members)

    @property
    def latitude(self) -> float:
        return self.latitude_sum / len(self.members)

    def add(self, item: VisualVerificationCaseRecord) -> None:
        observed_at = _utc(item.observed_at)
        self.members.append(item)
        self.longitude_sum += item.longitude
        self.latitude_sum += item.latitude
        self.start_at = observed_at if self.start_at is None else min(self.start_at, observed_at)
        self.end_at = observed_at if self.end_at is None else max(self.end_at, observed_at)


def _cluster_candidates(
    records: list[VisualVerificationCaseRecord],
    *,
    time_window: timedelta,
    spatial_radius_km: float,
) -> list[_Cluster]:
    clusters: list[_Cluster] = []
    active: list[_Cluster] = []
    for record in sorted(records, key=lambda item: (_utc(item.observed_at), item.source_candidate_id)):
        observed_at = _utc(record.observed_at)
        active = [
            cluster
            for cluster in active
            if cluster.end_at is not None and observed_at - cluster.end_at <= time_window
        ]
        nearby = [
            cluster
            for cluster in active
            if _haversine_km(
                record.longitude,
                record.latitude,
                cluster.longitude,
                cluster.latitude,
            )
            <= spatial_radius_km
        ]
        if nearby:
            cluster = min(
                nearby,
                key=lambda item: _haversine_km(
                    record.longitude,
                    record.latitude,
                    item.longitude,
                    item.latitude,
                ),
            )
        else:
            cluster = _Cluster()
            clusters.append(cluster)
            active.append(cluster)
        cluster.add(record)
    return clusters


def _clusters_from_upstream(
    records: list[VisualVerificationCaseRecord],
    *,
    time_window: timedelta,
    spatial_radius_km: float,
) -> tuple[list[_Cluster], bool]:
    supplied: dict[str, _Cluster] = {}
    fallback_records: list[VisualVerificationCaseRecord] = []
    for record in records:
        if record.source_cluster_id:
            cluster = supplied.setdefault(
                record.source_cluster_id,
                _Cluster(source_cluster_id=record.source_cluster_id),
            )
            cluster.add(record)
        else:
            fallback_records.append(record)
    return (
        [*supplied.values(), *_cluster_candidates(
            fallback_records,
            time_window=time_window,
            spatial_radius_km=spatial_radius_km,
        )],
        bool(supplied),
    )


def _cluster_point_count(cluster: _Cluster) -> int:
    supplied = [item.cluster_point_count for item in cluster.members if item.cluster_point_count]
    return max(supplied) if supplied else len(cluster.members)


def _cluster_confidence(cluster: _Cluster) -> float | None:
    supplied = [
        item.cluster_mean_confidence
        for item in cluster.members
        if item.cluster_mean_confidence is not None
    ]
    if supplied:
        return round(sum(supplied) / len(supplied), 4)
    values = [
        value
        for item in cluster.members
        if (value := _number(item.product_fields, "confidence_score", "confidence"))
        is not None
    ]
    return round(sum(values) / len(values), 4) if values else None


def _cluster_max_frp(cluster: _Cluster) -> float | None:
    supplied = [
        item.cluster_max_frp_mw
        for item in cluster.members
        if item.cluster_max_frp_mw is not None
    ]
    if supplied:
        return max(supplied)
    values = [
        value
        for item in cluster.members
        if (value := _number(item.product_fields, "frp_mw", "frp")) is not None
    ]
    return max(values) if values else None


def select_representative_candidates(
    event_id: str,
    records: list[VisualVerificationCaseRecord],
    request: FirePointSelectionRequest,
) -> FirePointSelectionResult:
    clusters, used_upstream_clusters = _clusters_from_upstream(
        records,
        time_window=timedelta(minutes=request.time_window_minutes),
        spatial_radius_km=request.spatial_radius_km,
    )
    eligible = [
        cluster for cluster in clusters if _cluster_point_count(cluster) >= request.minimum_cluster_points
    ]
    used_singleton_fallback = not eligible and bool(clusters)
    ranked_pool = eligible or clusters
    ranked_pool.sort(
        key=lambda cluster: (
            cluster.start_at or datetime.max.replace(tzinfo=UTC),
            -_cluster_point_count(cluster),
            -(_cluster_confidence(cluster) or 0.0),
            -(_cluster_max_frp(cluster) or 0.0),
        )
    )

    selected: list[SelectedFirePointCandidate] = []
    for rank, cluster in enumerate(ranked_pool[: request.max_results], start=1):
        representative = min(
            cluster.members,
            key=lambda item: (_utc(item.observed_at), item.source_candidate_id),
        )
        selected.append(
            SelectedFirePointCandidate(
                visual_case_id=representative.visual_case_id,
                source_candidate_id=representative.source_candidate_id,
                observed_at=_utc(representative.observed_at),
                ignition_point=GeoJsonPoint(
                    coordinates=(representative.longitude, representative.latitude)
                ),
                cluster_start_at=cluster.start_at,
                cluster_end_at=cluster.end_at,
                cluster_point_count=_cluster_point_count(cluster),
                cluster_mean_confidence=_cluster_confidence(cluster),
                cluster_max_frp_mw=_cluster_max_frp(cluster),
                imagery_status=representative.imagery_status,
                selection_rank=rank,
                selection_reason=(
                    "earliest spatially coherent hotspot cluster"
                    if not used_singleton_fallback
                    else "earliest available candidate; no cluster met the minimum point count"
                ),
                is_simulated=representative.is_simulated,
            )
        )
    return FirePointSelectionResult(
        event_id=event_id,
        selection_method=(
            "upstream_cluster_v1"
            if used_upstream_clusters
            else "earliest_spatiotemporal_cluster_v1"
        ),
        evaluated_candidate_count=len(records),
        eligible_cluster_count=len(eligible),
        used_singleton_fallback=used_singleton_fallback,
        selected=selected,
    )


async def select_event_fire_points(
    db: AsyncSession,
    *,
    event_id: str,
    request: FirePointSelectionRequest,
) -> FirePointSelectionResult:
    latest_versions = (
        select(
            VisualVerificationCaseRecord.event_id.label("event_id"),
            VisualVerificationCaseRecord.source_candidate_id.label("source_candidate_id"),
            func.max(VisualVerificationCaseRecord.version).label("max_version"),
        )
        .where(VisualVerificationCaseRecord.event_id == event_id)
        .group_by(
            VisualVerificationCaseRecord.event_id,
            VisualVerificationCaseRecord.source_candidate_id,
        )
        .subquery()
    )
    statement = (
        select(VisualVerificationCaseRecord)
        .join(
            latest_versions,
            (VisualVerificationCaseRecord.event_id == latest_versions.c.event_id)
            & (
                VisualVerificationCaseRecord.source_candidate_id
                == latest_versions.c.source_candidate_id
            )
            & (VisualVerificationCaseRecord.version == latest_versions.c.max_version),
        )
        .where(
            VisualVerificationCaseRecord.event_id == event_id,
            VisualVerificationCaseRecord.upstream_status.notin_(["rejected", "expired"]),
            VisualVerificationCaseRecord.status.notin_(["confirmed", "rejected"]),
        )
    )
    if request.start_at is not None:
        statement = statement.where(VisualVerificationCaseRecord.observed_at >= request.start_at)
    if request.end_at is not None:
        statement = statement.where(VisualVerificationCaseRecord.observed_at <= request.end_at)
    if request.require_imagery:
        statement = statement.where(VisualVerificationCaseRecord.imagery_status == "available")
    result = await db.execute(
        statement.order_by(
            VisualVerificationCaseRecord.observed_at,
            VisualVerificationCaseRecord.source_candidate_id,
        ).limit(request.candidate_limit)
    )
    return select_representative_candidates(
        event_id,
        list(result.scalars().all()),
        request,
    )


async def list_confirmed_fire_points(
    db: AsyncSession,
    *,
    event_id: str,
    current_only: bool = True,
    limit: int = 100,
) -> list[ConfirmedFirePointRead]:
    statement = (
        select(FireConfirmationRecord, VisualVerificationCaseRecord.event_id)
        .join(
            VisualVerificationCaseRecord,
            FireConfirmationRecord.visual_case_id
            == VisualVerificationCaseRecord.visual_case_id,
        )
        .where(
            VisualVerificationCaseRecord.event_id == event_id,
            FireConfirmationRecord.status == "confirmed",
        )
    )
    if current_only:
        statement = statement.where(FireConfirmationRecord.is_current.is_(True))
    rows = (
        await db.execute(
            statement.order_by(FireConfirmationRecord.confirmed_at.desc()).limit(limit)
        )
    ).all()
    return [
        ConfirmedFirePointRead(
            confirmation_id=record.confirmation_id,
            event_id=row_event_id,
            source_candidate_id=record.source_candidate_id,
            confirmed_at=record.confirmed_at,
            ignition_point=GeoJsonPoint(coordinates=(record.longitude, record.latitude)),
            confidence=record.confidence,
            evidence_ids=record.evidence_ids,
            confirmation_method=record.confirmation_method,
            rule_version=record.rule_version,
            is_simulated=record.is_simulated,
        )
        for record, row_event_id in rows
    ]
