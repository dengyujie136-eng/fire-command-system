from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.review_service import build_disaster_review

router = APIRouter(prefix="/review", tags=["review"])


@router.get("/events/{event_id}/analysis")
async def disaster_review(event_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    return {"ok": True, "data": await build_disaster_review(db, event_id)}