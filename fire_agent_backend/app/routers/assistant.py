from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.assistant_service import AssistantChatRequest, run_assistant_chat

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/chat")
async def assistant_chat(request: AssistantChatRequest, db: AsyncSession = Depends(get_db)) -> dict:
    return {"ok": True, "data": await run_assistant_chat(db, request)}