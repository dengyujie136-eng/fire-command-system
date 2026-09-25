import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import rasterio
import numpy as np
from PIL import Image
from rasterio.enums import Resampling
from rasterio.warp import transform_bounds
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.visual_verification.candidate_service import (
    CandidateConflictError,
    create_reverification_version,
    get_visual_case,
    ingest_candidate_envelope,
    list_candidate_history,
    list_case_assets,
    list_visual_cases,
)
from app.visual_verification.schemas import (
    CandidateIngestBatchResult,
    HotspotCandidateEnvelope,
    expected_firms_viirs_snpp_candidate_id,
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
    ImageryCatalogRead,
    CandidateImageryMatchRead,
    EvidenceFusionRunRead,
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
from app.visual_verification.imagery_catalog_service import (
    list_catalog_assets,
    list_candidate_matches,
)
from app.visual_verification.models import (
    FireConfirmationRecord,
    ImageryAssetCatalogRecord,
    VisualCaseAssetRecord,
    VisualVerificationCaseRecord,
)
from app.visual_verification.evidence_fusion_service import (
    list_evidence_fusions,
    persist_evidence_fusion,
)
from app.services.realtime_service import fetch_firms_area_hotspots


router = APIRouter(prefix="/visual-verification", tags=["visual-verification"])


def _local_imagery_phase(path: Path) -> str:
    name = path.stem.lower()
    if "_during_" in name:
        return "during"
    if "_pre_" in name:
        return "pre"
    if "_post_" in name:
        return "post"
    return "context"


def _local_imagery_time(event_id: str, phase: str) -> datetime | None:
    if event_id != "dixie_fire_2021":
        return None
    values = {
        "pre": datetime(2021, 7, 10, 0, 0, tzinfo=UTC),
        "during": datetime(2021, 7, 18, 18, 49, 21, tzinfo=UTC),
        "post": datetime(2021, 9, 22, 0, 0, tzinfo=UTC),
    }
    return values.get(phase)


@router.post("/events/{event_id}/discover-local-imagery")
async def discover_local_imagery(
    event_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Catalog georeferenced imagery already installed under the event directory."""

    settings = get_settings()
    event_root = settings.resolved_data_dir / "raw" / "sentinel2" / event_id
    if not event_root.is_dir():
        return {"ok": True, "data": {"event_id": event_id, "discovered": 0, "registered": 0, "linked": 0}}

    paths = sorted(path for path in event_root.rglob("*") if path.is_file() and path.suffix.lower() in {".tif", ".tiff"})
    catalog = list((await db.execute(select(ImageryAssetCatalogRecord).where(ImageryAssetCatalogRecord.event_id == event_id))).scalars().all())
    by_uri = {item.content_uri.removeprefix("data://").replace("\\", "/"): item for item in catalog}
    cases = list((await db.execute(select(VisualVerificationCaseRecord).where(VisualVerificationCaseRecord.event_id == event_id))).scalars().all())
    registered = 0
    linked = 0

    for path in paths:
        relative = path.relative_to(settings.resolved_data_dir).as_posix()
        try:
            with rasterio.open(path) as raster:
                if raster.crs is None or raster.count < 1:
                    continue
                west, south, east, north = transform_bounds(raster.crs, "EPSG:4326", *raster.bounds)
                descriptions = [value.upper() for value in raster.descriptions if value]
                bands = descriptions if len(descriptions) == raster.count else (["R", "G", "B"] if raster.count == 3 else [f"BAND_{index}" for index in range(1, raster.count + 1)])
                crs = str(raster.crs)
                resolution = max(abs(raster.res[0]), abs(raster.res[1]))
        except rasterio.errors.RasterioError:
            continue

        phase = _local_imagery_phase(path)
        acquired_at = _local_imagery_time(event_id, phase)
        asset = by_uri.get(relative)
        if asset is None:
            digest = hashlib.sha256(f"{event_id}:{relative}".encode()).hexdigest()[:28]
            asset = ImageryAssetCatalogRecord(
                asset_id=f"local_{digest}",
                event_id=event_id,
                source_name=path.stem,
                source_type="repository_geotiff",
                analysis_phase=phase,
                mime_type="image/tiff",
                time_start=acquired_at,
                time_end=acquired_at,
                content_uri=relative,
                footprint_geojson={"type": "Polygon", "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]]},
                crs=crs,
                resolution_m=resolution,
                bands=bands,
                quality_status="available",
                checksum_sha256=None,
                metadata_json={
                    "local_path": str(path),
                    "discovery": "event_directory_scan_v1",
                    "acquired_at": acquired_at.isoformat().replace("+00:00", "Z") if acquired_at else None,
                },
                is_simulated=False,
            )
            db.add(asset)
            await db.flush()
            by_uri[relative] = asset
            registered += 1
        else:
            asset.metadata_json = {
                **(asset.metadata_json or {}),
                "local_path": str(path),
                "discovery": "event_directory_scan_v1",
                "acquired_at": acquired_at.isoformat().replace("+00:00", "Z") if acquired_at else None,
            }

        role = {"pre": "comparison_pre", "during": "primary", "post": "comparison_post"}.get(phase, "context")
        for case in cases:
            if not (west <= case.longitude <= east and south <= case.latitude <= north):
                continue
            exists = await db.scalar(select(VisualCaseAssetRecord).where(
                VisualCaseAssetRecord.visual_case_id == case.visual_case_id,
                VisualCaseAssetRecord.source_asset_id == asset.asset_id,
                VisualCaseAssetRecord.asset_role == role,
            ))
            if exists is not None:
                continue
            db.add(VisualCaseAssetRecord(
                visual_case_id=case.visual_case_id,
                source_asset_id=asset.asset_id,
                asset_role=role,
                source_type=asset.source_type,
                source_name=asset.source_name,
                mime_type=asset.mime_type,
                acquired_at=asset.time_start,
                content_uri=asset.content_uri,
                quality_status=asset.quality_status,
                checksum_sha256=asset.checksum_sha256,
                is_simulated=False,
            ))
            linked += 1

    await db.commit()
    return {"ok": True, "data": {"event_id": event_id, "discovered": len(paths), "registered": registered, "linked": linked}}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@router.post("/events/{event_id}/bootstrap-local-data")
async def bootstrap_local_verification_data(
    event_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Register repository-managed candidates and imagery that already exist on disk."""

    settings = get_settings()
    manifest_path = settings.resolved_data_dir / "manifests" / f"{event_id}_visual_candidates.json"
    imagery_path = (
        settings.resolved_data_dir
        / "raw"
        / "sentinel2"
        / event_id
        / "gee"
        / f"{event_id}_s2_rgb_during_overview.tif"
    )
    if not manifest_path.is_file():
        raise HTTPException(404, f"候选火点清单不存在：{manifest_path.name}")
    if not imagery_path.is_file():
        raise HTTPException(404, f"灾中核验影像不存在：{imagery_path.name}")

    try:
        raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        with rasterio.open(imagery_path) as raster:
            if raster.crs is None or raster.count < 3:
                raise HTTPException(422, "核验 GeoTIFF 缺少坐标参考或 RGB 波段")
            west, south, east, north = transform_bounds(raster.crs, "EPSG:4326", *raster.bounds)
            crs = str(raster.crs)
            resolution_m = max(abs(raster.res[0]), abs(raster.res[1]))
    except (OSError, ValueError, rasterio.errors.RasterioError) as exc:
        raise HTTPException(422, f"无法读取本地核验数据：{exc}") from exc

    candidates = raw_manifest.get("candidates") or []
    if not candidates:
        raise HTTPException(422, "候选火点清单为空")
    content_uri = "data://" + imagery_path.relative_to(settings.resolved_data_dir).as_posix()
    footprint = {
        "type": "Polygon",
        "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
    }
    checksum = _sha256(imagery_path)
    asset_id = f"{event_id}-sentinel2-during-overview"
    for candidate in candidates:
        longitude = float(candidate["location"]["longitude"])
        latitude = float(candidate["location"]["latitude"])
        if not (west <= longitude <= east and south <= latitude <= north):
            raise HTTPException(422, f"核验影像不覆盖候选点：{candidate['candidate_id']}")
        candidate["imagery_status"] = "available"
        candidate["imagery_refs"] = [
            {
                "asset_id": asset_id,
                "uri": content_uri,
                "source": "Sentinel-2 RGB during-fire overview",
                "mime_type": "image/tiff",
                "acquired_at": "2021-07-18T18:49:21.024000Z",
                "time_start": "2021-07-13T00:00:00Z",
                "time_end": "2021-07-21T23:59:59Z",
                "analysis_phase": "during",
                "footprint_geojson": footprint,
                "crs": crs,
                "resolution_m": resolution_m,
                "bands": ["R", "G", "B"],
                "quality_status": "usable",
                "checksum_sha256": checksum,
            }
        ]
    envelope = HotspotCandidateEnvelope.model_validate(raw_manifest)
    try:
        result = await ingest_candidate_envelope(db, envelope)
        await db.commit()
    except CandidateConflictError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "ok": True,
        "data": {
            "event_id": event_id,
            "candidate_count": len(result.items),
            "asset_id": asset_id,
            "imagery_file": imagery_path.name,
            "actions": [item.action.value for item in result.items],
        },
    }


def _asset_phase_label(asset) -> str:
    phase = {
        "comparison_pre": "灾前背景影像",
        "primary": "灾中候选火点影像",
        "comparison_post": "灾后变化影像",
        "context": "上下文影像",
    }.get(asset.asset_role, asset.asset_role)
    return f"{phase}；资产={asset.source_asset_id}；来源={asset.source_name or 'unknown'}"


def _asset_phase_order(asset) -> tuple[int, str]:
    return ({"comparison_pre": 0, "primary": 1, "comparison_post": 2}.get(asset.asset_role, 3), asset.source_asset_id)


def _derivative_labels(derivatives, assets) -> dict[str, str]:
    assets_by_id = {asset.source_asset_id: asset for asset in assets}
    return {
        item.derivative_id: _asset_phase_label(assets_by_id[item.source_asset_id])
        if item.source_asset_id in assets_by_id
        else f"遥感影像；资产={item.source_asset_id}"
        for item in derivatives
    }


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


@router.get("/events/{event_id}/imagery-catalog", response_model=list[ImageryCatalogRead])
async def imagery_catalog(
    event_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[ImageryCatalogRead]:
    records = await list_catalog_assets(db, event_id=event_id)
    return [ImageryCatalogRead.model_validate(record) for record in records]


@router.get("/imagery-catalog/{asset_id}/preview", response_class=FileResponse)
async def imagery_catalog_preview(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    asset = await db.scalar(select(ImageryAssetCatalogRecord).where(ImageryAssetCatalogRecord.asset_id == asset_id))
    if asset is None:
        raise HTTPException(404, "影像资产不存在")
    settings = get_settings()
    relative = asset.content_uri.removeprefix("data://")
    source = (settings.resolved_data_dir / relative).resolve()
    if not source.is_relative_to(settings.resolved_data_dir.resolve()) or not source.is_file():
        raise HTTPException(404, "影像文件不存在")

    output_dir = settings.resolved_visual_output_dir / "catalog-previews"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{hashlib.sha256(asset_id.encode()).hexdigest()[:24]}.jpg"
    if not output.is_file() or output.stat().st_mtime < source.stat().st_mtime:
        try:
            with rasterio.open(source) as raster:
                if raster.count < 3:
                    raise HTTPException(422, "当前影像不足三个可视化波段")
                scale = min(1.0, 1600 / max(raster.width, raster.height))
                width = max(1, round(raster.width * scale))
                height = max(1, round(raster.height * scale))
                def normalize_band_name(value: str | None) -> str:
                    name = str(value or '').upper()
                    return f"B0{name[1:]}" if name.startswith("B") and len(name) == 2 else name

                raster_band_names = [normalize_band_name(value) for value in raster.descriptions]
                catalog_band_names = [normalize_band_name(value) for value in (asset.bands or [])]
                band_names = raster_band_names if any(raster_band_names) else catalog_band_names
                natural_color_indexes = [1, 2, 3]
                if {"B02", "B03", "B04"} <= set(band_names):
                    natural_color_indexes = [
                        band_names.index("B04") + 1,
                        band_names.index("B03") + 1,
                        band_names.index("B02") + 1,
                    ]
                values = raster.read(
                    natural_color_indexes,
                    out_shape=(3, height, width),
                    resampling=Resampling.bilinear,
                    masked=True,
                ).astype(np.float32)
                rgb = np.zeros((3, height, width), dtype=np.uint8)
                for index in range(3):
                    band = values[index]
                    valid = band.compressed()
                    if not valid.size:
                        continue
                    low, high = np.percentile(valid, [2, 98])
                    if high <= low:
                        high = low + 1
                    normalized = np.clip((band.filled(low) - low) / (high - low), 0, 1)
                    rgb[index] = (normalized * 255).astype(np.uint8)
                Image.fromarray(np.moveaxis(rgb, 0, -1), mode="RGB").save(output, "JPEG", quality=88, optimize=True)
        except rasterio.errors.RasterioError as exc:
            raise HTTPException(422, f"无法生成影像预览：{exc}") from exc
    return FileResponse(output, media_type="image/jpeg", filename=f"{asset_id}.jpg")


@router.post("/imagery-catalog/{asset_id}/extract-candidates")
async def extract_catalog_image_candidates(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Query FIRMS for the selected image footprint and persist those observations as candidates."""

    asset = await db.scalar(select(ImageryAssetCatalogRecord).where(ImageryAssetCatalogRecord.asset_id == asset_id))
    if asset is None:
        raise HTTPException(404, "影像资产不存在")
    if asset.analysis_phase not in {"during", "primary"}:
        raise HTTPException(422, "只有灾中影像可以提取当前火点候选")

    footprint = asset.footprint_geojson or {}
    rings = footprint.get("coordinates") or []
    ring = rings[0] if footprint.get("type") == "Polygon" and rings else []
    if len(ring) < 4:
        raise HTTPException(422, "所选影像缺少可用的 WGS84 覆盖范围")
    longitudes = [float(point[0]) for point in ring]
    latitudes = [float(point[1]) for point in ring]
    bbox = (min(longitudes), min(latitudes), max(longitudes), max(latitudes))

    now = datetime.now(UTC)
    acquired_at_value = (asset.metadata_json or {}).get("acquired_at")
    acquired_at = None
    if acquired_at_value:
        try:
            acquired_at = datetime.fromisoformat(str(acquired_at_value).replace("Z", "+00:00"))
        except ValueError:
            acquired_at = None
    if acquired_at is None:
        start_at = asset.time_start or asset.time_end or now
        end_at = asset.time_end or asset.time_start or start_at
        if start_at.tzinfo is None:
            start_at = start_at.replace(tzinfo=UTC)
        if end_at.tzinfo is None:
            end_at = end_at.replace(tzinfo=UTC)
        acquired_at = start_at + (end_at - start_at) / 2
    elif acquired_at.tzinfo is None:
        acquired_at = acquired_at.replace(tzinfo=UTC)
    else:
        acquired_at = acquired_at.astimezone(UTC)
    try:
        firms = await fetch_firms_area_hotspots(
            bbox=bbox,
            start_date=acquired_at.date(),
            end_date=acquired_at.date(),
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc

    event_case = await db.scalar(
        select(VisualVerificationCaseRecord)
        .where(VisualVerificationCaseRecord.event_id == asset.event_id)
        .order_by(VisualVerificationCaseRecord.created_at.desc())
    )
    event_name = event_case.event_name if event_case is not None else asset.event_id

    def inside_footprint(longitude: float, latitude: float) -> bool:
        inside = False
        previous = ring[-1]
        for current in ring:
            x1, y1 = float(previous[0]), float(previous[1])
            x2, y2 = float(current[0]), float(current[1])
            if (y1 > latitude) != (y2 > latitude):
                intersection = (x2 - x1) * (latitude - y1) / (y2 - y1) + x1
                if longitude < intersection:
                    inside = not inside
            previous = current
        return inside

    temporal_window = timedelta(hours=12)
    time_matched_hotspots = [
        hotspot
        for hotspot in firms["hotspots"]
        if abs(hotspot["observed_at"] - acquired_at) <= temporal_window
    ]
    grouped: dict[tuple[int, int], list[dict]] = {}
    for hotspot in time_matched_hotspots:
        longitude = float(hotspot["longitude"])
        latitude = float(hotspot["latitude"])
        if inside_footprint(longitude, latitude):
            grouped.setdefault((round(longitude / 0.01), round(latitude / 0.01)), []).append(hotspot)

    representatives = []
    for observations in grouped.values():
        representative = max(
            observations,
            key=lambda item: (
                float(item.get("confidence") or 0),
                float(item.get("frp_mw") or 0),
                item["observed_at"],
            ),
        )
        representatives.append((representative, observations))
    representatives.sort(
        key=lambda item: (
            float(item[0].get("confidence") or 0),
            float(item[0].get("frp_mw") or 0),
            item[0]["observed_at"],
        ),
        reverse=True,
    )
    representatives = representatives[:100]

    candidates = []
    for hotspot, observations in representatives:
        longitude = float(hotspot["longitude"])
        latitude = float(hotspot["latitude"])
        observed_at = hotspot["observed_at"]
        candidate_id = expected_firms_viirs_snpp_candidate_id(
            asset.event_id,
            observed_at,
            latitude,
            longitude,
        )
        confidences = [float(item.get("confidence") or 0) for item in observations]
        frp_values = [float(item["frp_mw"]) for item in observations if item.get("frp_mw") is not None]
        historical_replay = hotspot["source_product"] == "VIIRS_SNPP_SP"
        candidates.append({
                "schema_version": "fire.hotspot.candidate.v0.1",
                "candidate_id": candidate_id,
                "event_id": asset.event_id,
                "event_name": event_name,
                "location": {"longitude": longitude, "latitude": latitude, "crs": "EPSG:4326"},
                "observed_at": observed_at,
                "source_cluster_id": f"firms-area-{asset_id}-{round(longitude / 0.01)}-{round(latitude / 0.01)}",
                "cluster_point_count": len(observations),
                "cluster_mean_confidence": sum(confidences) / len(confidences),
                "cluster_max_frp_mw": max(frp_values) if frp_values else None,
                "status": "candidate",
                "data_owner": {
                    "organization": "NASA FIRMS",
                    "source_product": hotspot["source_product"],
                    "license": "NASA FIRMS attribution required",
                    "attribution_required": True,
                },
                "imagery_status": "available",
                "imagery_refs": [{
                    "asset_id": asset.asset_id,
                    "uri": asset.content_uri,
                    "source": asset.source_name,
                    "mime_type": asset.mime_type or "image/tiff",
                    "acquired_at": acquired_at,
                    "time_start": asset.time_start,
                    "time_end": asset.time_end,
                    "analysis_phase": "during",
                    "footprint_geojson": asset.footprint_geojson,
                    "crs": asset.crs,
                    "resolution_m": asset.resolution_m,
                    "bands": asset.bands,
                    "quality_status": "usable",
                    "checksum_sha256": asset.checksum_sha256,
                }],
                "is_simulated": False,
                "replay": {
                    "is_replay": historical_replay,
                    "replay_interval_minutes": 10 if historical_replay else None,
                    "replay_source": "NASA FIRMS standard-processing area API" if historical_replay else None,
                },
                "product_fields": {
                    "algorithm": "firms_area_api_candidate_selection_v1",
                    "source": "NASA FIRMS Area API",
                    "source_product": hotspot["source_product"],
                    "source_record_id": hotspot["source_record_id"],
                    "frp_mw": hotspot.get("frp_mw"),
                    "brightness_ti4": hotspot.get("brightness_ti4"),
                    "brightness_ti5": hotspot.get("brightness_ti5"),
                    "satellite": hotspot.get("satellite"),
                    "instrument": hotspot.get("instrument"),
                    "daynight": hotspot.get("daynight"),
                    "selection_method": "highest confidence and FRP observation per approximately 1 km grid cell",
                    "source_asset_id": asset_id,
                },
            })

    envelope = HotspotCandidateEnvelope.model_validate({
        "schema_version": "fire.hotspot.candidate.v0.1",
        "event_id": asset.event_id,
        "generated_at": now,
        "candidates": candidates,
    })
    result = await ingest_candidate_envelope(db, envelope)
    active_items = [item for item in result.items if item.case.upstream_status != "rejected"]
    await db.commit()
    return {
        "ok": True,
        "data": {
            "asset_id": asset_id,
            "algorithm": "firms_area_api_candidate_selection_v1",
            "source": "NASA FIRMS Area API",
            "source_product": firms["source_product"],
            "imagery_acquired_at": acquired_at.isoformat().replace("+00:00", "Z"),
            "query_start_date": firms["start_date"],
            "query_end_date": firms["end_date"],
            "api_observation_count": firms["total"],
            "temporal_window_hours": 12,
            "time_matched_observation_count": len(time_matched_hotspots),
            "footprint_observation_count": sum(len(items) for items in grouped.values()),
            "representative_count": len(representatives),
            "selection_method": "highest confidence and FRP observation per approximately 1 km grid cell; maximum 100 candidates",
            "candidate_count": len(active_items),
            "candidates": [item.case.model_dump(mode="json") for item in active_items],
        },
    }


@router.post("/imagery-catalog/{asset_id}/auto-detect")
async def auto_detect_catalog_candidates(
    asset_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Automatically test ranked FIRMS candidates until fire/smoke evidence is found."""
    candidate_ids = [str(value) for value in (payload.get("candidate_ids") or []) if value]
    if not candidate_ids:
        raise HTTPException(422, "candidate_ids 不能为空")
    limit = min(max(int(payload.get("max_candidates") or 20), 1), 100)
    crop_radius_m = min(max(float(payload.get("crop_radius_m") or 3000), 500), 10000)
    settings = get_settings()
    attempts: list[dict] = []
    selected: dict | None = None
    for visual_case_id in candidate_ids[:limit]:
        case = await get_visual_case(db, visual_case_id)
        if case is None:
            continue
        if case.status in {"confirmed", "rejected"}:
            case = await create_reverification_version(
                db,
                case,
                reason="operator_started_target_detection",
            )
            visual_case_id = case.visual_case_id
        assets = await list_case_assets(db, visual_case_id)
        source = next((item for item in assets if item.source_asset_id == asset_id), None)
        if source is None:
            continue
        try:
            _prepared, derivative, _created = await prepare_case_asset_derivative(
                db,
                visual_case_id=visual_case_id,
                source_asset_id=asset_id,
                options=DerivativePreparationOptions(
                    crop_radius_m=crop_radius_m,
                    source_kind="geotiff",
                    output_format="jpeg",
                    max_dimension=1536,
                    thumbnail_dimension=512,
                    jpeg_quality=90,
                ),
                source_root=settings.resolved_data_dir,
                output_root=settings.resolved_visual_output_dir,
            )
            detector_payload = await ProfessionalDetectorClient(
                settings.professional_detector_api_url,
                settings.professional_detector_timeout_seconds,
            ).detect(
                [(derivative.derivative_id, _derivative_path(derivative.file_uri))],
                confidence_threshold=settings.professional_detector_default_confidence,
                image_size=640,
            )
            result = await persist_professional_detection(
                db,
                visual_case_id=visual_case_id,
                derivative_ids=[derivative.derivative_id],
                payload=detector_payload,
                is_simulated=bool(case.is_simulated or source.is_simulated),
            )
            attempts.append({
                "visual_case_id": visual_case_id,
                "source_candidate_id": case.source_candidate_id,
                "longitude": case.longitude,
                "latitude": case.latitude,
                "derivative": VisualImageDerivativeRead.model_validate(derivative).model_dump(mode="json"),
                "professional": result.model_dump(mode="json"),
            })
            if result.professional.support == FindingSupport.SUPPORTS_FIRE:
                selected = attempts[-1]
                break
        except (ImageProcessingError, ProfessionalDetectorError) as exc:
            await db.rollback()
            attempts.append({"visual_case_id": visual_case_id, "error": str(exc)})
    await db.commit()
    return {
        "ok": True,
        "asset_id": asset_id,
        "attempted_count": len(attempts),
        "selected": selected,
        "attempts": attempts,
        "status": "detected" if selected else "no_detection",
    }


@router.get(
    "/candidates/{visual_case_id}/imagery-matches",
    response_model=list[CandidateImageryMatchRead],
)
async def candidate_imagery_matches(
    visual_case_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[CandidateImageryMatchRead]:
    records = await list_candidate_matches(db, visual_case_id=visual_case_id)
    return [CandidateImageryMatchRead.model_validate(record) for record in records]


@router.get(
    "/candidates/{visual_case_id}/fusion-runs",
    response_model=list[EvidenceFusionRunRead],
)
async def candidate_fusion_runs(
    visual_case_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[EvidenceFusionRunRead]:
    records = await list_evidence_fusions(db, visual_case_id=visual_case_id)
    return [EvidenceFusionRunRead.model_validate(record) for record in records]


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


@router.delete("/candidates/{visual_case_id}")
async def exclude_candidate(
    visual_case_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Exclude a candidate from active verification while retaining its audit records."""
    record = await get_visual_case(db, visual_case_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visual case not found")
    record.upstream_status = "rejected"
    record.product_fields = {
        **dict(record.product_fields or {}),
        "excluded_from_verification": True,
        "excluded_at": datetime.now(UTC).isoformat(),
        "exclusion_method": "human_review",
    }
    confirmations = (
        await db.execute(
            select(FireConfirmationRecord).where(
                FireConfirmationRecord.visual_case_id == visual_case_id,
                FireConfirmationRecord.is_current.is_(True),
            )
        )
    ).scalars().all()
    for confirmation in confirmations:
        confirmation.is_current = False
    await db.commit()
    return {"ok": True, "data": {"visual_case_id": visual_case_id, "status": "excluded"}}


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

    assets = await list_case_assets(db, visual_case_id)
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
        image_labels=_derivative_labels(derivatives, assets),
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
    assets = await list_case_assets(db, visual_case_id)
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
            image_labels=_derivative_labels(derivatives, assets),
            prompt_version=QWEN_FIRE_PROMPT_VERSION,
        ),
    )
    fusion = await persist_evidence_fusion(
        db,
        case=case,
        visual=visual,
        professional=professional,
    )
    decision = review_decision(
        visual,
        professional,
        assume_screened_candidate_is_fire=settings.visual_auto_confirm_screened_candidates,
        minimum_confirmation_confidence=settings.visual_auto_confirm_min_confidence,
        fusion_score=fusion.final_score,
        fusion_run_id=fusion.fusion_run_id,
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
        fusion_run_id=fusion.fusion_run_id,
        fusion_score=fusion.final_score,
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
        ordered_assets = sorted(assets, key=_asset_phase_order)
        selected_assets = []
        seen_roles: set[str] = set()
        for asset in ordered_assets:
            if asset.asset_role in seen_roles:
                continue
            selected_assets.append(asset)
            seen_roles.add(asset.asset_role)
            if len(selected_assets) == 3:
                break
        derivatives = []
        try:
            for asset in selected_assets:
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
                derivatives.append(derivative)
        except ImageProcessingError as exc:
            await db.rollback()
            raise _processing_http_error(exc) from exc
        review = await _execute_complete_review(
            selected.visual_case_id,
            VisualReviewStartRequest(
                derivative_ids=[item.derivative_id for item in derivatives],
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
