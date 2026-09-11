from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
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
    ImageAnalysisRequest,
    VisualAnalysisFailure,
    VisualAnalysisResult,
    VisualAnalysisStartRequest,
)
from app.visual_verification.analysis_service import execute_and_persist_visual_analysis
from app.visual_verification.provider_factory import (
    QwenConfigurationError,
    build_qwen_provider,
)
from app.visual_verification.qwen_prompt import QWEN_FIRE_PROMPT_VERSION
from app.visual_verification.image_processing.errors import (
    DerivativeConflictError,
    ImageProcessingError,
    SourceImageNotFoundError,
    VisualAssetNotFoundError,
    VisualCaseNotFoundError,
)
from app.visual_verification.image_processing.paths import SafeImagePathResolver
from app.visual_verification.image_processing.schemas import (
    DerivativePreparationOptions,
    ImageProcessingResult,
    VisualImageDerivativeRead,
)
from app.visual_verification.image_processing.workflow import (
    get_derivative,
    prepare_case_asset_derivative,
)
from app.visual_verification.states import VisualCaseStatus


router = APIRouter(prefix="/visual-verification", tags=["visual-verification"])


def _processing_http_error(exc: ImageProcessingError) -> HTTPException:
    if isinstance(
        exc,
        (VisualCaseNotFoundError, VisualAssetNotFoundError, SourceImageNotFoundError),
    ):
        response_status = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, DerivativeConflictError):
        response_status = status.HTTP_409_CONFLICT
    else:
        response_status = status.HTTP_422_UNPROCESSABLE_CONTENT
    return HTTPException(
        status_code=response_status,
        detail={"code": exc.code, "message": exc.message},
    )


def _derivative_path(uri: str) -> Path:
    settings = get_settings()
    resolver = SafeImagePathResolver(
        settings.resolved_data_dir,
        settings.resolved_visual_output_dir,
    )
    return resolver.resolve_output(uri)


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


@router.post(
    "/candidates/{visual_case_id}/assets/{source_asset_id}/derivatives",
    response_model=ImageProcessingResult,
)
async def prepare_derivative(
    visual_case_id: str,
    source_asset_id: str,
    payload: DerivativePreparationOptions,
    db: AsyncSession = Depends(get_db),
) -> ImageProcessingResult:
    settings = get_settings()
    try:
        result, _record, _created = await prepare_case_asset_derivative(
            db,
            visual_case_id=visual_case_id,
            source_asset_id=source_asset_id,
            options=payload,
            source_root=settings.resolved_data_dir,
            output_root=settings.resolved_visual_output_dir,
        )
        await db.commit()
        return result
    except ImageProcessingError as exc:
        await db.rollback()
        raise _processing_http_error(exc) from exc


@router.get(
    "/derivatives/{derivative_id}",
    response_model=VisualImageDerivativeRead,
)
async def derivative_detail(
    derivative_id: str,
    db: AsyncSession = Depends(get_db),
) -> VisualImageDerivativeRead:
    record = await get_derivative(db, derivative_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Visual derivative not found")
    return VisualImageDerivativeRead.model_validate(record)


@router.get("/derivatives/{derivative_id}/image", response_class=FileResponse)
async def derivative_image(
    derivative_id: str,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    record = await get_derivative(db, derivative_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Visual derivative not found")
    try:
        return FileResponse(_derivative_path(record.file_uri))
    except ImageProcessingError as exc:
        raise _processing_http_error(exc) from exc


@router.get("/derivatives/{derivative_id}/preview", response_class=FileResponse)
async def derivative_preview(
    derivative_id: str,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    record = await get_derivative(db, derivative_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Visual derivative not found")
    if not record.preview_uri:
        raise HTTPException(status_code=404, detail="Visual derivative preview not found")
    try:
        return FileResponse(_derivative_path(record.preview_uri))
    except ImageProcessingError as exc:
        raise _processing_http_error(exc) from exc


@router.post(
    "/candidates/{visual_case_id}/analyses",
    response_model=VisualAnalysisResult | VisualAnalysisFailure,
)
async def run_visual_analysis(
    visual_case_id: str,
    payload: VisualAnalysisStartRequest,
    db: AsyncSession = Depends(get_db),
) -> VisualAnalysisResult | VisualAnalysisFailure:
    derivatives = []
    for derivative_id in payload.derivative_ids:
        derivative = await get_derivative(db, derivative_id)
        if derivative is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Visual derivative not found: {derivative_id}",
            )
        if derivative.visual_case_id != visual_case_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Derivative does not belong to visual case: {derivative_id}",
            )
        derivatives.append(derivative)

    settings = get_settings()
    try:
        provider = build_qwen_provider(settings)
    except QwenConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "qwen_not_configured", "message": str(exc)},
        ) from exc

    request = ImageAnalysisRequest(
        visual_case_id=visual_case_id,
        image_asset_ids=[item.derivative_id for item in derivatives],
        image_uris={item.derivative_id: item.file_uri for item in derivatives},
        prompt_version=QWEN_FIRE_PROMPT_VERSION,
    )
    result = await execute_and_persist_visual_analysis(
        db,
        provider=provider,
        request=request,
    )
    await db.commit()
    return result
