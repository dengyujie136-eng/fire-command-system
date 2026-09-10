from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.visual_verification.candidate_service import (
    CandidateConflictError,
    get_visual_case,
    ingest_candidate_envelope,
    list_candidate_history,
    list_case_assets,
    list_visual_cases,
)
from app.visual_verification.schemas import (
    CandidateIngestBatchResult,
    HotspotCandidateEnvelope,
    UpstreamCandidateStatus,
    UpstreamImageryStatus,
    VisualCaseAssetRead,
    VisualCaseDetail,
    VisualCaseRead,
)
from app.visual_verification.states import VisualCaseStatus


router = APIRouter(prefix="/visual-verification", tags=["visual-verification"])


@router.post("/candidates/import", response_model=CandidateIngestBatchResult)
async def import_candidates(
    payload: HotspotCandidateEnvelope,
    db: AsyncSession = Depends(get_db),
) -> CandidateIngestBatchResult:
    try:
        result = await ingest_candidate_envelope(db, payload)
        await db.commit()
        return result
    except CandidateConflictError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/candidates", response_model=list[VisualCaseRead])
async def candidates(
    event_id: str | None = None,
    visual_status: VisualCaseStatus | None = None,
    upstream_status: UpstreamCandidateStatus | None = None,
    imagery_status: UpstreamImageryStatus | None = None,
    include_history: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> list[VisualCaseRead]:
    records = await list_visual_cases(
        db,
        event_id=event_id,
        visual_status=visual_status.value if visual_status else None,
        upstream_status=upstream_status.value if upstream_status else None,
        imagery_status=imagery_status.value if imagery_status else None,
        include_history=include_history,
        limit=limit,
    )
    return [VisualCaseRead.model_validate(record) for record in records]


@router.get(
    "/candidates/source/{event_id}/{source_candidate_id}/history",
    response_model=list[VisualCaseRead],
)
async def candidate_history(
    event_id: str,
    source_candidate_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[VisualCaseRead]:
    records = await list_candidate_history(
        db,
        event_id=event_id,
        source_candidate_id=source_candidate_id,
    )
    return [VisualCaseRead.model_validate(record) for record in records]


@router.get("/candidates/{visual_case_id}", response_model=VisualCaseDetail)
async def candidate_detail(
    visual_case_id: str,
    db: AsyncSession = Depends(get_db),
) -> VisualCaseDetail:
    record = await get_visual_case(db, visual_case_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visual case not found")
    assets = await list_case_assets(db, visual_case_id)
    return VisualCaseDetail(
        case=VisualCaseRead.model_validate(record),
        assets=[VisualCaseAssetRead.model_validate(asset) for asset in assets],
    )
