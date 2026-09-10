from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.recommendation import (
    RecommendationEnvelope,
    RecommendationPackageRead,
    RecommendationPayload,
    RecommendationRegenerateRequest,
    ResourceInventoryRead,
    RoutePlanRead,
    UavAssetRead,
)
from app.services.recommendation_service import latest_recommendations, regenerate_recommendations

router = APIRouter(prefix="/events/{event_id}/recommendations", tags=["recommendations"])


def _payload(data: dict) -> RecommendationPayload:
    return RecommendationPayload(
        package=RecommendationPackageRead.model_validate(data["package"]),
        routes=[RoutePlanRead.model_validate(item) for item in data.get("routes", [])],
        uavs=[UavAssetRead.model_validate(item) for item in data.get("uavs", [])],
        resources=[ResourceInventoryRead.model_validate(item) for item in data.get("resources", [])],
    )


@router.get("/latest", response_model=RecommendationEnvelope)
async def latest(event_id: str, db: AsyncSession = Depends(get_db)) -> RecommendationEnvelope:
    data = await latest_recommendations(db, event_id)
    return RecommendationEnvelope(data=_payload(data) if data else None)


@router.post("/regenerate", response_model=RecommendationEnvelope)
async def regenerate(
    event_id: str,
    request: RecommendationRegenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> RecommendationEnvelope:
    return RecommendationEnvelope(data=_payload(await regenerate_recommendations(db, event_id, request)))
