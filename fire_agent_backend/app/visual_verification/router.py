import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
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
    ProfessionalDetectionResult,
    ProfessionalDetectionStartRequest,
    VisualReviewResult,
    VisualReviewStartRequest,
    ProfessionalDetection,
    FindingSupport,
    RemoteSensingAnalysisRequest,
    RemoteSensingAnalysisType,
    RemoteSensingCapabilities,
    RemoteSensingCapability,
    RemoteSensingAnalysisRunRead,
    RemoteSensingChangeResult,
    RemoteSensingFireConfirmationResult,
    ConfirmedFirePointRead,
    FirePointSelectionRequest,
    FirePointSelectionResult,
    AutoConfirmFirePointsRequest,
    AutoConfirmFirePointsResult,
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
from app.visual_verification.professional_detector import (
    ProfessionalDetectorClient,
    ProfessionalDetectorError,
    persist_professional_detection,
)
from app.visual_verification.review_service import (
    mark_case_analyzing,
    persist_review_decision,
    review_decision,
)
from app.visual_verification.raster_change import RasterChangeAnalyzer
from app.visual_verification.remote_analysis_service import (
    complete_remote_analysis,
    fail_remote_analysis,
    get_remote_analysis,
    list_remote_analyses,
    start_remote_analysis,
)
from app.visual_verification.selection_service import (
    list_confirmed_fire_points,
    select_event_fire_points,
)


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


def _remote_sensing_capabilities() -> RemoteSensingCapabilities:
    return RemoteSensingCapabilities(
        capabilities=[
            RemoteSensingCapability(
                analysis_type=RemoteSensingAnalysisType.FIRE_CONFIRMATION,
                tool_name="analyze_fire_imagery",
                minimum_asset_count=1,
                execution_status="available",
                output_summary="Fire, flame, smoke, burn-scar and confidence evidence.",
            ),
            RemoteSensingCapability(
                analysis_type=RemoteSensingAnalysisType.TEMPORAL_CHANGE,
                tool_name="analyze_temporal_change",
                minimum_asset_count=2,
                execution_status="available",
                output_summary="Before/after remote-sensing change evidence.",
            ),
            RemoteSensingCapability(
                analysis_type=RemoteSensingAnalysisType.BURNED_AREA,
                tool_name="analyze_temporal_change",
                minimum_asset_count=2,
                execution_status="available",
                output_summary="Georeferenced burned-area geometry and area statistics.",
            ),
        ]
    )


@router.get("/analyses/capabilities", response_model=RemoteSensingCapabilities)
async def remote_sensing_capabilities() -> RemoteSensingCapabilities:
    """Describe the stable tools that member D can expose to the agent layer."""

    return _remote_sensing_capabilities()


@router.post(
    "/events/{event_id}/select-fire-points",
    response_model=FirePointSelectionResult,
)
async def select_fire_points(
    event_id: str,
    payload: FirePointSelectionRequest,
    db: AsyncSession = Depends(get_db),
) -> FirePointSelectionResult:
    """Select representative candidates for any event already loaded by the data agent."""

    return await select_event_fire_points(db, event_id=event_id, request=payload)


@router.get(
    "/events/{event_id}/confirmed-fire-points",
    response_model=list[ConfirmedFirePointRead],
)
async def confirmed_fire_points(
    event_id: str,
    current_only: bool = True,
    limit: int = Query(default=100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> list[ConfirmedFirePointRead]:
    """Return standard confirmed points for spread or multi-agent orchestration."""

    return await list_confirmed_fire_points(
        db,
        event_id=event_id,
        current_only=current_only,
        limit=limit,
    )


@router.get("/analyses", response_model=list[RemoteSensingAnalysisRunRead])
async def remote_sensing_analysis_history(
    event_id: str | None = None,
    visual_case_id: str | None = None,
    analysis_type: RemoteSensingAnalysisType | None = None,
    run_status: str | None = Query(default=None, pattern="^(running|succeeded|failed)$"),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> list[RemoteSensingAnalysisRunRead]:
    records = await list_remote_analyses(
        db,
        event_id=event_id,
        visual_case_id=visual_case_id,
        analysis_type=analysis_type,
        run_status=run_status,
        limit=limit,
    )
    return [RemoteSensingAnalysisRunRead.model_validate(record) for record in records]


@router.get("/analyses/{analysis_id}", response_model=RemoteSensingAnalysisRunRead)
async def remote_sensing_analysis_detail(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
) -> RemoteSensingAnalysisRunRead:
    record = await get_remote_analysis(db, analysis_id)
    if record is None:
        raise AppError(
            f"remote-sensing analysis not found: {analysis_id}",
            code="remote_analysis_not_found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return RemoteSensingAnalysisRunRead.model_validate(record)


@router.get(
    "/analyses/{analysis_id}/artifacts/{artifact_name}",
    response_class=FileResponse,
)
async def remote_sensing_analysis_artifact(
    analysis_id: str,
    artifact_name: str,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    record = await get_remote_analysis(db, analysis_id)
    if record is None:
        raise AppError(
            f"remote-sensing analysis not found: {analysis_id}",
            code="remote_analysis_not_found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    outputs = (record.result_payload or {}).get("output_uris", {})
    if not isinstance(outputs, dict) or artifact_name not in outputs:
        raise AppError(
            f"analysis artifact not found: {artifact_name}",
            code="remote_analysis_artifact_not_found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    try:
        return FileResponse(_derivative_path(str(outputs[artifact_name])))
    except ImageProcessingError as exc:
        raise AppError(
            exc.message,
            code=exc.code,
            status_code=status.HTTP_404_NOT_FOUND,
        ) from exc


@router.post(
    "/analyses/run",
    response_model=RemoteSensingFireConfirmationResult | RemoteSensingChangeResult,
)
async def run_remote_sensing_analysis(
    payload: RemoteSensingAnalysisRequest,
    db: AsyncSession = Depends(get_db),
) -> RemoteSensingFireConfirmationResult | RemoteSensingChangeResult:
    """Run an event-neutral analysis without hard-coding a fire event."""

    if payload.visual_case_id is None:
        raise AppError(
            "remote-sensing analysis currently requires a registered visual_case_id",
            code="visual_case_required",
            status_code=status.HTTP_409_CONFLICT,
        )
    if (
        payload.analysis_type == RemoteSensingAnalysisType.FIRE_CONFIRMATION
        and not payload.prepared_image_ids
    ):
        raise AppError(
            "registered imagery must be converted to model-ready derivatives first",
            code="imagery_not_prepared",
            status_code=status.HTTP_409_CONFLICT,
        )

    case = await get_visual_case(db, payload.visual_case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Visual case not found")
    if case.event_id != payload.event_id:
        raise AppError(
            "visual case does not belong to the requested event",
            code="event_case_mismatch",
            status_code=status.HTTP_409_CONFLICT,
        )

    if payload.analysis_type != RemoteSensingAnalysisType.FIRE_CONFIRMATION:
        assets = {
            item.source_asset_id: item
            for item in await list_case_assets(db, payload.visual_case_id)
            if item.source_asset_id in payload.asset_ids
        }
        missing_assets = [item for item in payload.asset_ids if item not in assets]
        if missing_assets:
            raise AppError(
                f"imagery assets are not registered for this event: {', '.join(missing_assets)}",
                code="imagery_asset_not_found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        before_asset = assets[payload.asset_ids[0]]
        after_asset = assets[payload.asset_ids[1]]
        is_simulated = (
            case.is_simulated
            or before_asset.is_simulated
            or after_asset.is_simulated
        )
        run_record = await start_remote_analysis(
            db,
            payload=payload,
            is_simulated=is_simulated,
        )
        await db.commit()
        settings = get_settings()
        try:
            result = await asyncio.to_thread(
                RasterChangeAnalyzer(
                    settings.resolved_data_dir,
                    settings.resolved_visual_output_dir,
                ).analyze,
                event_id=payload.event_id,
                analysis_type=payload.analysis_type,
                before_asset_id=before_asset.source_asset_id,
                before_uri=before_asset.content_uri,
                after_asset_id=after_asset.source_asset_id,
                after_uri=after_asset.content_uri,
                threshold=payload.change_threshold,
                minimum_region_pixels=payload.minimum_region_pixels,
                is_simulated=is_simulated,
                target_geometry_wgs84=(
                    payload.target_geometry.model_dump(mode="json")
                    if payload.target_geometry is not None
                    else None
                ),
                analysis_id=run_record.analysis_id,
            )
        except Exception as exc:
            await db.rollback()
            persisted_run = await get_remote_analysis(db, run_record.analysis_id)
            if persisted_run is not None:
                if isinstance(exc, ImageProcessingError):
                    error_code, error_message = exc.code, exc.message
                else:
                    error_code = "analysis_execution_failed"
                    error_message = str(exc)
                await fail_remote_analysis(
                    db,
                    persisted_run,
                    error_code=error_code,
                    error_message=error_message,
                )
                await db.commit()
            if isinstance(exc, ImageProcessingError):
                raise AppError(
                    exc.message,
                    code=exc.code,
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                ) from exc
            raise
        await complete_remote_analysis(db, run_record, result)
        await db.commit()
        return result

    derivatives = []
    for derivative_id in payload.prepared_image_ids:
        derivative = await get_derivative(db, derivative_id)
        if derivative is None:
            raise HTTPException(status_code=404, detail=f"Visual derivative not found: {derivative_id}")
        if derivative.visual_case_id != payload.visual_case_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Derivative does not belong to visual case: {derivative_id}",
            )
        derivatives.append(derivative)
    derivative_asset_ids = {item.source_asset_id for item in derivatives}
    if derivative_asset_ids != set(payload.asset_ids):
        raise AppError(
            "prepared images must correspond exactly to the requested asset_ids",
            code="asset_derivative_mismatch",
            status_code=status.HTTP_409_CONFLICT,
        )

    run_record = await start_remote_analysis(
        db,
        payload=payload,
        is_simulated=(
            case.is_simulated or any(item.is_simulated for item in derivatives)
        ),
    )
    await db.commit()
    try:
        review = await _execute_complete_review(
            payload.visual_case_id,
            VisualReviewStartRequest(derivative_ids=payload.prepared_image_ids),
            db,
        )
        result = RemoteSensingFireConfirmationResult(
            analysis_id=run_record.analysis_id,
            event_id=payload.event_id,
            analysis_type=RemoteSensingAnalysisType.FIRE_CONFIRMATION,
            source_asset_ids=payload.asset_ids,
            hotspot_ids=payload.hotspot_ids,
            review=review,
        )
        await complete_remote_analysis(db, run_record, result)
        await db.commit()
        return result
    except Exception as exc:
        await db.rollback()
        persisted_run = await get_remote_analysis(db, run_record.analysis_id)
        if persisted_run is not None:
            if isinstance(exc, AppError):
                error_code, error_message = exc.code, exc.message
            elif isinstance(exc, HTTPException):
                error_code, error_message = "http_error", str(exc.detail)
            else:
                error_code, error_message = "analysis_execution_failed", str(exc)
            await fail_remote_analysis(
                db,
                persisted_run,
                error_code=error_code,
                error_message=error_message,
            )
            await db.commit()
        raise


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


@router.post(
    "/candidates/{visual_case_id}/professional-detections",
    response_model=ProfessionalDetectionResult,
)
async def run_professional_detection(
    visual_case_id: str,
    payload: ProfessionalDetectionStartRequest,
    db: AsyncSession = Depends(get_db),
) -> ProfessionalDetectionResult:
    derivatives = []
    for derivative_id in payload.derivative_ids:
        derivative = await get_derivative(db, derivative_id)
        if derivative is None:
            raise HTTPException(status_code=404, detail=f"Visual derivative not found: {derivative_id}")
        if derivative.visual_case_id != visual_case_id:
            raise HTTPException(status_code=409, detail=f"Derivative does not belong to visual case: {derivative_id}")
        derivatives.append(derivative)

    settings = get_settings()
    confidence_threshold = (
        payload.confidence_threshold
        if payload.confidence_threshold is not None
        else settings.professional_detector_default_confidence
    )
    client = ProfessionalDetectorClient(
        settings.professional_detector_api_url,
        settings.professional_detector_timeout_seconds,
    )
    try:
        detector_payload = await client.detect(
            [(item.derivative_id, _derivative_path(item.file_uri)) for item in derivatives],
            confidence_threshold=confidence_threshold,
            image_size=payload.image_size,
        )
        result = await persist_professional_detection(
            db,
            visual_case_id=visual_case_id,
            derivative_ids=payload.derivative_ids,
            payload=detector_payload,
            is_simulated=any(item.is_simulated for item in derivatives),
        )
        await db.commit()
        return result
    except ProfessionalDetectorError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc


async def _execute_complete_review(
    visual_case_id: str,
    payload: VisualReviewStartRequest,
    db: AsyncSession,
) -> VisualReviewResult:
    case = await get_visual_case(db, visual_case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Visual case not found")
    derivatives = []
    for derivative_id in payload.derivative_ids:
        derivative = await get_derivative(db, derivative_id)
        if derivative is None:
            raise HTTPException(status_code=404, detail=f"Visual derivative not found: {derivative_id}")
        if derivative.visual_case_id != visual_case_id:
            raise HTTPException(status_code=409, detail=f"Derivative does not belong to visual case: {derivative_id}")
        derivatives.append(derivative)

    try:
        await mark_case_analyzing(db, case)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    settings = get_settings()
    confidence_threshold = (
        payload.detector_confidence_threshold
        if payload.detector_confidence_threshold is not None
        else settings.professional_detector_default_confidence
    )
    warnings: list[str] = []
    professional_run = None
    try:
        detector_payload = await ProfessionalDetectorClient(
            settings.professional_detector_api_url,
            settings.professional_detector_timeout_seconds,
        ).detect(
            [(item.derivative_id, _derivative_path(item.file_uri)) for item in derivatives],
            confidence_threshold=confidence_threshold,
            image_size=payload.detector_image_size,
        )
        professional_run = await persist_professional_detection(
            db,
            visual_case_id=visual_case_id,
            derivative_ids=payload.derivative_ids,
            payload=detector_payload,
            is_simulated=any(item.is_simulated for item in derivatives),
        )
        professional = professional_run.professional
    except ProfessionalDetectorError as exc:
        warnings.append(exc.code)
        professional = ProfessionalDetection(
            support=FindingSupport.UNAVAILABLE,
            evidence_ids=[],
            summary=exc.message,
        )

    try:
        provider = build_qwen_provider(settings)
    except QwenConfigurationError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=503,
            detail={"code": "qwen_not_configured", "message": str(exc)},
        ) from exc
    visual = await execute_and_persist_visual_analysis(
        db,
        provider=provider,
        request=ImageAnalysisRequest(
            visual_case_id=visual_case_id,
            image_asset_ids=payload.derivative_ids,
            image_uris={item.derivative_id: item.file_uri for item in derivatives},
            prompt_version=QWEN_FIRE_PROMPT_VERSION,
        ),
    )
    decision = review_decision(
        visual,
        professional,
        assume_screened_candidate_is_fire=settings.visual_auto_confirm_screened_candidates,
        minimum_confirmation_confidence=settings.visual_auto_confirm_min_confidence,
    )
    is_simulated = case.is_simulated or any(item.is_simulated for item in derivatives)
    confirmation = await persist_review_decision(
        db,
        case=case,
        decision=decision,
        is_simulated=is_simulated,
    )
    await db.commit()
    return VisualReviewResult(
        visual_case_id=visual_case_id,
        visual=visual,
        professional_run=professional_run,
        professional=professional,
        confirmation=decision,
        confirmation_id=confirmation.confirmation_id,
        warnings=warnings,
        is_simulated=is_simulated,
    )


@router.post(
    "/candidates/{visual_case_id}/review",
    response_model=VisualReviewResult,
)
async def run_complete_review(
    visual_case_id: str,
    payload: VisualReviewStartRequest,
    db: AsyncSession = Depends(get_db),
) -> VisualReviewResult:
    return await _execute_complete_review(visual_case_id, payload, db)


@router.post(
    "/events/{event_id}/auto-confirm-fire-points",
    response_model=AutoConfirmFirePointsResult,
)
async def auto_confirm_fire_points(
    event_id: str,
    payload: AutoConfirmFirePointsRequest,
    db: AsyncSession = Depends(get_db),
) -> AutoConfirmFirePointsResult:
    """Select, prepare, run Qwen/detector and persist fire points for any event."""

    selection = await select_event_fire_points(
        db,
        event_id=event_id,
        request=payload.selection,
    )
    settings = get_settings()
    reviews: list[VisualReviewResult] = []
    confirmation_ids: set[str] = set()
    for selected in selection.selected:
        assets = await list_case_assets(db, selected.visual_case_id)
        if not assets:
            raise AppError(
                f"selected candidate has no registered imagery: {selected.source_candidate_id}",
                code="selected_candidate_imagery_missing",
                status_code=status.HTTP_409_CONFLICT,
            )
        asset = next((item for item in assets if item.asset_role == "primary"), assets[0])
        try:
            _prepared, derivative, _created = await prepare_case_asset_derivative(
                db,
                visual_case_id=selected.visual_case_id,
                source_asset_id=asset.source_asset_id,
                options=DerivativePreparationOptions(
                    crop_radius_m=payload.crop_radius_m,
                    band_indexes=payload.band_indexes,
                ),
                source_root=settings.resolved_data_dir,
                output_root=settings.resolved_visual_output_dir,
            )
        except ImageProcessingError as exc:
            await db.rollback()
            raise _processing_http_error(exc) from exc
        review = await _execute_complete_review(
            selected.visual_case_id,
            VisualReviewStartRequest(
                derivative_ids=[derivative.derivative_id],
                detector_confidence_threshold=payload.detector_confidence_threshold,
                detector_image_size=payload.detector_image_size,
            ),
            db,
        )
        reviews.append(review)
        confirmation_ids.add(review.confirmation_id)

    confirmed = await list_confirmed_fire_points(
        db,
        event_id=event_id,
        current_only=True,
        limit=max(100, len(confirmation_ids)),
    )
    return AutoConfirmFirePointsResult(
        event_id=event_id,
        selection=selection,
        reviews=reviews,
        confirmed_fire_points=[
            item for item in confirmed if item.confirmation_id in confirmation_ids
        ],
    )
