from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.visual_verification.models import RemoteSensingAnalysisRecord
from app.visual_verification.schemas import (
    RemoteSensingAnalysisRequest,
    RemoteSensingAnalysisType,
    RemoteSensingChangeResult,
    RemoteSensingFireConfirmationResult,
)


def _tool_name(analysis_type: RemoteSensingAnalysisType) -> str:
    if analysis_type == RemoteSensingAnalysisType.FIRE_CONFIRMATION:
        return "analyze_fire_imagery"
    return "analyze_temporal_change"


async def start_remote_analysis(
    db: AsyncSession,
    *,
    payload: RemoteSensingAnalysisRequest,
    is_simulated: bool,
) -> RemoteSensingAnalysisRecord:
    record = RemoteSensingAnalysisRecord(
        analysis_id=f"remote-analysis-{uuid4().hex}",
        visual_case_id=payload.visual_case_id,
        event_id=payload.event_id,
        analysis_type=payload.analysis_type.value,
        tool_name=_tool_name(payload.analysis_type),
        run_status="running",
        source_asset_ids=payload.asset_ids,
        request_payload=payload.model_dump(mode="json"),
        started_at=datetime.now(UTC),
        is_simulated=is_simulated,
    )
    db.add(record)
    await db.flush()
    return record


async def complete_remote_analysis(
    db: AsyncSession,
    record: RemoteSensingAnalysisRecord,
    result: RemoteSensingChangeResult | RemoteSensingFireConfirmationResult,
) -> RemoteSensingAnalysisRecord:
    if result.analysis_id != record.analysis_id:
        raise ValueError("analysis result ID does not match the persisted run")
    if result.event_id != record.event_id:
        raise ValueError("analysis result event does not match the persisted run")
    if result.analysis_type.value != record.analysis_type:
        raise ValueError("analysis result type does not match the persisted run")
    if isinstance(result, RemoteSensingChangeResult):
        result_assets = [result.before_asset_id, result.after_asset_id]
    else:
        result_assets = result.source_asset_ids
    if result_assets != record.source_asset_ids:
        raise ValueError("analysis result assets do not match the persisted run")

    finished_at = datetime.now(UTC)
    record.run_status = "succeeded"
    record.result_payload = result.model_dump(mode="json")
    record.finished_at = finished_at
    record.duration_ms = max(
        0,
        int((finished_at - _as_utc(record.started_at)).total_seconds() * 1000),
    )
    await db.flush()
    return record


async def fail_remote_analysis(
    db: AsyncSession,
    record: RemoteSensingAnalysisRecord,
    *,
    error_code: str,
    error_message: str,
) -> RemoteSensingAnalysisRecord:
    finished_at = datetime.now(UTC)
    record.run_status = "failed"
    record.error_code = error_code
    record.error_message = error_message[:4000]
    record.finished_at = finished_at
    record.duration_ms = max(
        0,
        int((finished_at - _as_utc(record.started_at)).total_seconds() * 1000),
    )
    await db.flush()
    return record


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def get_remote_analysis(
    db: AsyncSession,
    analysis_id: str,
) -> RemoteSensingAnalysisRecord | None:
    return await db.scalar(
        select(RemoteSensingAnalysisRecord).where(
            RemoteSensingAnalysisRecord.analysis_id == analysis_id
        )
    )


async def list_remote_analyses(
    db: AsyncSession,
    *,
    event_id: str | None = None,
    visual_case_id: str | None = None,
    analysis_type: RemoteSensingAnalysisType | None = None,
    run_status: str | None = None,
    limit: int = 100,
) -> list[RemoteSensingAnalysisRecord]:
    statement = select(RemoteSensingAnalysisRecord)
    if event_id is not None:
        statement = statement.where(RemoteSensingAnalysisRecord.event_id == event_id)
    if visual_case_id is not None:
        statement = statement.where(
            RemoteSensingAnalysisRecord.visual_case_id == visual_case_id
        )
    if analysis_type is not None:
        statement = statement.where(
            RemoteSensingAnalysisRecord.analysis_type == analysis_type.value
        )
    if run_status is not None:
        statement = statement.where(RemoteSensingAnalysisRecord.run_status == run_status)
    result = await db.execute(
        statement.order_by(desc(RemoteSensingAnalysisRecord.created_at)).limit(
            max(1, min(limit, 500))
        )
    )
    return list(result.scalars().all())
