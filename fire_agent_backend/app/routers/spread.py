from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.session import get_db
from app.schemas.spread import FireFrontStepRead, SimulationRunRead, SpreadEnvelope, SpreadRunPayload, SpreadRunRequest
from app.services.spread_service import create_spread_run, latest_spread_run, spread_steps

router = APIRouter(tags=["spread"])


def _payload(data: dict) -> SpreadRunPayload:
    return SpreadRunPayload(
        run=SimulationRunRead.model_validate(data["run"]),
        steps=[FireFrontStepRead.model_validate(item) for item in data.get("steps", [])],
        geojson=data.get("geojson", {"type": "FeatureCollection", "features": []}),
    )


@router.post("/events/{event_id}/spread-runs", response_model=SpreadEnvelope)
async def create(event_id: str, request: SpreadRunRequest, db: AsyncSession = Depends(get_db)) -> SpreadEnvelope:
    return SpreadEnvelope(data=_payload(await create_spread_run(db, event_id, request)))


@router.get("/events/{event_id}/spread-runs/latest", response_model=SpreadEnvelope)
async def latest(event_id: str, db: AsyncSession = Depends(get_db)) -> SpreadEnvelope:
    data = await latest_spread_run(db, event_id)
    return SpreadEnvelope(data=_payload(data) if data else None)


@router.get("/spread-runs/{run_id}/steps", response_model=SpreadEnvelope)
async def steps(run_id: str, db: AsyncSession = Depends(get_db)) -> SpreadEnvelope:
    items = await spread_steps(db, run_id)
    if not items:
        raise AppError(f"Spread run not found or has no steps: {run_id}", code="spread_run_not_found", status_code=404)
    return SpreadEnvelope(data=[FireFrontStepRead.model_validate(item) for item in items])
