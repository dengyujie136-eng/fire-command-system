from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.recalculation import (
    DisturbanceEnvelope,
    RecalculationEnvelope,
    RecalculationPayload,
    RecalculationRequest,
    RecalculationRunRead,
    ScenarioDisturbanceCreate,
    ScenarioDisturbanceRead,
)
from app.schemas.recommendation import RecommendationPackageRead, RecommendationPayload, ResourceInventoryRead, RoutePlanRead, UavAssetRead
from app.services.recalculation_service import create_disturbance, latest_recalculation, recalculate

router = APIRouter(tags=["recalculations"])


def _recommendation_payload(data: dict) -> RecommendationPayload:
    return RecommendationPayload(
        package=RecommendationPackageRead.model_validate(data["package"]),
        routes=[RoutePlanRead.model_validate(item) for item in data.get("routes", [])],
        uavs=[UavAssetRead.model_validate(item) for item in data.get("uavs", [])],
        resources=[ResourceInventoryRead.model_validate(item) for item in data.get("resources", [])],
    )


def _recalculation_payload(data: dict) -> RecalculationPayload:
    return RecalculationPayload(
        disturbance=ScenarioDisturbanceRead.model_validate(data["disturbance"]),
        recalculation=RecalculationRunRead.model_validate(data["recalculation"]),
        recommendation=_recommendation_payload(data["recommendation"]),
    )


@router.post("/events/{event_id}/disturbances", response_model=DisturbanceEnvelope)
async def create(event_id: str, request: ScenarioDisturbanceCreate, db: AsyncSession = Depends(get_db)) -> DisturbanceEnvelope:
    return DisturbanceEnvelope(data=ScenarioDisturbanceRead.model_validate(await create_disturbance(db, event_id, request)))


@router.post("/events/{event_id}/recalculate", response_model=RecalculationEnvelope)
async def run_recalculation(event_id: str, request: RecalculationRequest, db: AsyncSession = Depends(get_db)) -> RecalculationEnvelope:
    return RecalculationEnvelope(data=_recalculation_payload(await recalculate(db, event_id, request)))


@router.get("/events/{event_id}/recalculations/latest", response_model=RecalculationEnvelope)
async def latest(event_id: str, db: AsyncSession = Depends(get_db)) -> RecalculationEnvelope:
    data = await latest_recalculation(db, event_id)
    return RecalculationEnvelope(data=_recalculation_payload(data) if data else None)
