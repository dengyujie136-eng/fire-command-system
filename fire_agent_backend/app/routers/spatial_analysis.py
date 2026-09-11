from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.spatial_analysis import (
    EmergencyRoutePlanRead,
    SpatialAnalysisEnvelope,
    SpatialAnalysisPayload,
    SpatialAnalysisRequest,
    SpatialAnalysisRunRead,
    SpatialImpactRecordRead,
)
from app.services.spatial_analysis_service import create_spatial_analysis, latest_spatial_analysis

router = APIRouter(tags=["spatial-analysis"])


def _payload(data: dict) -> SpatialAnalysisPayload:
    return SpatialAnalysisPayload(
        run=SpatialAnalysisRunRead.model_validate(data["run"]),
        impacts=[SpatialImpactRecordRead.model_validate(item) for item in data.get("impacts", [])],
        routes=[EmergencyRoutePlanRead.model_validate(item) for item in data.get("routes", [])],
    )


@router.post("/events/{event_id}/spatial-analysis", response_model=SpatialAnalysisEnvelope)
async def create(
    event_id: str,
    request: SpatialAnalysisRequest,
    db: AsyncSession = Depends(get_db),
) -> SpatialAnalysisEnvelope:
    return SpatialAnalysisEnvelope(data=_payload(await create_spatial_analysis(db, event_id, request)))


@router.get("/events/{event_id}/spatial-analysis/latest", response_model=SpatialAnalysisEnvelope)
async def latest(event_id: str, db: AsyncSession = Depends(get_db)) -> SpatialAnalysisEnvelope:
    data = await latest_spatial_analysis(db, event_id)
    return SpatialAnalysisEnvelope(data=_payload(data) if data else None)
