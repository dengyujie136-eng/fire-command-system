from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.spread import SpreadRunRequest
from app.services.workflow_service import rerun_spread_workflow, start_historical_fire_workflow

router = APIRouter(tags=["workflows"])


class WorkflowRerunSpreadRequest(SpreadRunRequest):
    include_report: bool = False


class HistoricalWorkflowStartRequest(BaseModel):
    include_report: bool = True


@router.post("/events/{event_id}/workflow/rerun-spread")
async def rerun_spread(
    event_id: str,
    request: WorkflowRerunSpreadRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    spread_request = SpreadRunRequest(**request.model_dump(exclude={"include_report"}))
    return {"ok": True, "data": await rerun_spread_workflow(db, event_id, spread_request, include_report=request.include_report)}


@router.post("/historical-events/{historical_event_id}/workflow/start")
async def start_historical_workflow(
    historical_event_id: str,
    request: HistoricalWorkflowStartRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    return {"ok": True, "data": await start_historical_fire_workflow(db, historical_event_id, include_report=request.include_report)}
