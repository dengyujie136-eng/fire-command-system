from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.integrations.schemas import CommandWorkflowEnvelope, CommandWorkflowRequest
from app.services.command_workflow_service import (
    latest_command_workflow,
    run_command_workflow,
)


router = APIRouter(tags=["command-workflow"])


@router.post(
    "/events/{event_id}/command-workflow",
    response_model=CommandWorkflowEnvelope,
)
async def run(
    event_id: str,
    request: CommandWorkflowRequest,
    db: AsyncSession = Depends(get_db),
) -> CommandWorkflowEnvelope:
    result = await run_command_workflow(db, event_id, request)
    return CommandWorkflowEnvelope(data=result)


@router.get(
    "/events/{event_id}/command-workflow/latest",
    response_model=CommandWorkflowEnvelope,
)
async def latest(
    event_id: str,
    db: AsyncSession = Depends(get_db),
) -> CommandWorkflowEnvelope:
    return CommandWorkflowEnvelope(data=await latest_command_workflow(db, event_id))
