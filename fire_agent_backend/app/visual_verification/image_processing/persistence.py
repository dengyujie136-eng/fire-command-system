from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.visual_verification.image_processing.errors import DerivativeConflictError
from app.visual_verification.image_processing.schemas import ImageProcessingResult
from app.visual_verification.models import VisualImageDerivativeRecord


async def persist_derivative(
    db: AsyncSession,
    result: ImageProcessingResult,
) -> tuple[VisualImageDerivativeRecord, bool]:
    """Persist one deterministic derivative, returning (record, created)."""

    existing = await db.scalar(
        select(VisualImageDerivativeRecord).where(
            VisualImageDerivativeRecord.derivative_id == result.derivative_id
        )
    )
    if existing is not None:
        if (
            existing.visual_case_id != result.visual_case_id
            or existing.source_asset_id != result.source_asset_id
            or existing.checksum_sha256 != result.output_sha256
        ):
            raise DerivativeConflictError(
                "derivative_id is already associated with different content"
            )
        return existing, False

    processing_parameters = dict(result.processing_parameters)
    processing_parameters.update({
        "schema_version": result.schema_version,
        "parameter_sha256": result.parameter_sha256,
        "source_sha256": result.source_sha256,
        "source_kind": result.source_kind,
        "source_size": result.source_size.model_dump(),
        "output_size": result.output_size.model_dump(),
        "preview_size": result.preview_size.model_dump(),
        "pixel_window": result.pixel_window.model_dump() if result.pixel_window else None,
        "band_indexes": result.band_indexes,
        "nodata_ratio": result.nodata_ratio,
        "metadata_uri": result.metadata_uri,
        "preview_sha256": result.preview_sha256,
        "processing_purpose": result.processing_purpose,
        "warnings": result.warnings,
    })
    record = VisualImageDerivativeRecord(
        derivative_id=result.derivative_id,
        visual_case_id=result.visual_case_id,
        source_asset_id=result.source_asset_id,
        derivative_type="candidate_crop",
        file_uri=result.output_uri,
        preview_uri=result.preview_uri,
        crs=result.crs,
        extent_geojson=result.actual_extent_geojson,
        processing_parameters=processing_parameters,
        checksum_sha256=result.output_sha256,
        is_simulated=result.is_simulated,
    )
    db.add(record)
    await db.flush()
    return record, True
