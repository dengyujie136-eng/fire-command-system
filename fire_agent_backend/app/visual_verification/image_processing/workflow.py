from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.visual_verification.image_processing.errors import (
    ImageryNotReadyError,
    UnsupportedImageError,
    VisualAssetNotFoundError,
    VisualCaseNotFoundError,
)
from app.visual_verification.image_processing.persistence import persist_derivative
from app.visual_verification.image_processing.schemas import (
    DerivativePreparationOptions,
    ImageCropRequest,
    ImageProcessingResult,
)
from app.visual_verification.image_processing.service import ImageProcessingService
from app.visual_verification.models import (
    VisualCaseAssetRecord,
    VisualImageDerivativeRecord,
    VisualVerificationCaseRecord,
)


async def prepare_case_asset_derivative(
    db: AsyncSession,
    *,
    visual_case_id: str,
    source_asset_id: str,
    options: DerivativePreparationOptions,
    source_root: Path,
    output_root: Path,
) -> tuple[ImageProcessingResult, VisualImageDerivativeRecord, bool]:
    """Resolve trusted case/asset identity, prepare the image, and persist its lineage."""

    case = await db.scalar(
        select(VisualVerificationCaseRecord).where(
            VisualVerificationCaseRecord.visual_case_id == visual_case_id
        )
    )
    if case is None:
        raise VisualCaseNotFoundError(f"visual case does not exist: {visual_case_id}")
    if case.imagery_status != "available":
        raise ImageryNotReadyError(
            f"visual case imagery is {case.imagery_status}; available imagery is required"
        )

    asset = await db.scalar(
        select(VisualCaseAssetRecord).where(
            VisualCaseAssetRecord.visual_case_id == visual_case_id,
            VisualCaseAssetRecord.source_asset_id == source_asset_id,
        )
    )
    if asset is None:
        raise VisualAssetNotFoundError(
            f"asset {source_asset_id!r} is not attached to visual case {visual_case_id!r}"
        )

    try:
        request = ImageCropRequest(
            visual_case_id=case.visual_case_id,
            source_asset_id=asset.source_asset_id,
            source_uri=asset.content_uri,
            imagery_status=case.imagery_status,
            longitude=case.longitude,
            latitude=case.latitude,
            is_simulated=case.is_simulated or asset.is_simulated,
            **options.model_dump(),
        )
    except ValidationError as exc:
        raise UnsupportedImageError(
            "stored case or asset metadata cannot form a safe image processing request"
        ) from exc
    result = await run_in_threadpool(
        ImageProcessingService(source_root, output_root).process,
        request,
    )
    record, created = await persist_derivative(db, result)
    return result, record, created


async def get_derivative(
    db: AsyncSession,
    derivative_id: str,
) -> VisualImageDerivativeRecord | None:
    return await db.scalar(
        select(VisualImageDerivativeRecord).where(
            VisualImageDerivativeRecord.derivative_id == derivative_id
        )
    )
