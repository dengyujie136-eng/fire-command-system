from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.spatial_analysis import (
    EmergencyRoutePlanRead,
    SpatialAnalysisPayload,
    SpatialAnalysisRequest,
    SpatialAnalysisRunRead,
    SpatialImpactRecordRead,
)
from app.services.spatial_analysis_service import create_spatial_analysis


class SpatialRiskAdapter:
    """Invoke member C's spatial engine and normalize its persisted result."""

    async def run(
        self,
        db: AsyncSession,
        *,
        event_id: str,
        spread_run_id: str,
        threat_buffer_km: float,
    ) -> SpatialAnalysisPayload:
        data = await create_spatial_analysis(
            db,
            event_id,
            SpatialAnalysisRequest(
                threat_buffer_km=threat_buffer_km,
                include_routes=False,
                input_source=f"agent_spread:{spread_run_id}",
            ),
        )
        return SpatialAnalysisPayload(
            run=SpatialAnalysisRunRead.model_validate(data["run"]),
            impacts=[
                SpatialImpactRecordRead.model_validate(item)
                for item in data.get("impacts", [])
            ],
            routes=[
                EmergencyRoutePlanRead.model_validate(item)
                for item in data.get("routes", [])
            ],
        )
