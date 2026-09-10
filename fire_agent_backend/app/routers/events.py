from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.event import EventEnvelope, FireEventDetail, FireEventRead, StartSimulatedEventRequest
from app.services.event_service import (
    close_event,
    create_simulated_event,
    get_current_event,
    get_event_or_404,
    list_timeline,
)

router = APIRouter(prefix="/events", tags=["events"])


@router.post("/simulated/start", response_model=EventEnvelope)
async def start_simulated_event(
    request: StartSimulatedEventRequest,
    db: AsyncSession = Depends(get_db),
) -> EventEnvelope:
    event = await create_simulated_event(db, request)
    return EventEnvelope(data=FireEventRead.model_validate(event))


@router.get("/current", response_model=EventEnvelope)
async def current_event(db: AsyncSession = Depends(get_db)) -> EventEnvelope:
    event = await get_current_event(db)
    return EventEnvelope(data=FireEventRead.model_validate(event) if event else None)


@router.get("/{event_id}", response_model=EventEnvelope)
async def event_detail(event_id: str, db: AsyncSession = Depends(get_db)) -> EventEnvelope:
    event = await get_event_or_404(db, event_id)
    timeline = await list_timeline(db, event_id)
    return EventEnvelope(
        data=FireEventDetail(
            event=FireEventRead.model_validate(event),
            timeline=[item for item in timeline],
        )
    )


@router.get("/{event_id}/timeline", response_model=EventEnvelope)
async def event_timeline(event_id: str, db: AsyncSession = Depends(get_db)) -> EventEnvelope:
    timeline = await list_timeline(db, event_id)
    return EventEnvelope(data=timeline)


@router.post("/{event_id}/close", response_model=EventEnvelope)
async def close_fire_event(event_id: str, db: AsyncSession = Depends(get_db)) -> EventEnvelope:
    event = await close_event(db, event_id)
    return EventEnvelope(data=FireEventRead.model_validate(event))
