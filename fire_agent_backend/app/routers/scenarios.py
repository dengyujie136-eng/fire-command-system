from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.scenario import ScenarioEnvelope, ScenarioRead
from app.services.scenario_registry import list_scenarios

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("", response_model=ScenarioEnvelope)
async def scenarios(db: AsyncSession = Depends(get_db)) -> ScenarioEnvelope:
    return ScenarioEnvelope(data=[ScenarioRead.model_validate(item) for item in await list_scenarios(db)])
