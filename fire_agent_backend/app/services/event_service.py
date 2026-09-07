from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Select, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.event import EventTimeline, FireEvent
from app.models.scenario import SimulationClock
from app.schemas.event import StartSimulatedEventRequest
from app.services.scenario_registry import get_scenario_or_404
from app.services.websocket_manager import websocket_manager


ACTIVE_STATUSES = {"created", "observing", "confirmed", "simulating", "deciding", "dispatching", "replanning", "failed"}


def _event_public_payload(event: FireEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "name": event.name,
        "status": event.status,
        "scenario_id": event.scenario_id,
        "source_mode": event.source_mode,
        "ignition_point": {
            "longitude": event.ignition_longitude,
            "latitude": event.ignition_latitude,
            "confidence": event.ignition_confidence,
        },
    }


async def append_timeline(
    db: AsyncSession,
    *,
    event_id: str,
    event_type: str,
    status: str,
    title: str,
    message: str,
    payload: dict[str, Any] | None = None,
    broadcast: bool = True,
) -> EventTimeline:
    item = EventTimeline(
        timeline_id=f"tl_{uuid4().hex}",
        event_id=event_id,
        event_type=event_type,
        status=status,
        title=title,
        message=message,
        payload=payload or {},
    )
    db.add(item)
    await db.flush()

    if broadcast:
        await websocket_manager.broadcast_event(
            event_id,
            "timeline.created",
            {
                "timeline_id": item.timeline_id,
                "event_id": event_id,
                "event_type": event_type,
                "status": status,
                "title": title,
                "message": message,
                "payload": item.payload,
            },
        )
    return item


async def create_simulated_event(db: AsyncSession, request: StartSimulatedEventRequest) -> FireEvent:
    scenario = await get_scenario_or_404(db, request.scenario_id)
    ignition_point = request.ignition_point
    ignition_longitude = ignition_point.longitude if ignition_point else scenario.longitude
    ignition_latitude = ignition_point.latitude if ignition_point else scenario.latitude
    ignition_confidence = ignition_point.confidence if ignition_point else 0.87
    event_name = request.name or f"{scenario.name} active event"

    event = FireEvent(
        event_id=f"evt_{uuid4().hex[:16]}",
        name=event_name,
        status="created",
        scenario_id=scenario.scenario_id,
        source_mode="simulation",
        ignition_longitude=ignition_longitude,
        ignition_latitude=ignition_latitude,
        ignition_confidence=ignition_confidence,
        metadata_json={
            "is_simulated": True,
            "data_source_mode": "simulation",
            "scenario_location_name": scenario.location_name,
            "coordinate_precision": scenario.coordinate_precision,
            **request.metadata,
        },
    )
    db.add(event)
    await db.flush()
    db.add(
        SimulationClock(
            event_id=event.event_id,
            scenario_id=scenario.scenario_id,
            status="idle",
            current_minute=0,
            duration_minutes=scenario.duration_minutes,
            tick_interval_seconds=scenario.default_tick_interval_seconds,
            time_segments=scenario.time_segments,
        )
    )
    await append_timeline(
        db,
        event_id=event.event_id,
        event_type="event.created",
        status=event.status,
        title="Fire event created",
        message="A trusted fire point event has been created as the root event for the emergency workflow.",
        payload=_event_public_payload(event),
        broadcast=False,
    )
    await db.commit()
    await db.refresh(event)
    await websocket_manager.broadcast_event(event.event_id, "event.created", _event_public_payload(event))
    await websocket_manager.broadcast_system_event("event.created", _event_public_payload(event))
    return event


async def get_event_or_404(db: AsyncSession, event_id: str) -> FireEvent:
    result = await db.execute(select(FireEvent).where(FireEvent.event_id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise AppError(f"Fire event not found: {event_id}", code="event_not_found", status_code=404)
    return event


async def get_current_event(db: AsyncSession) -> FireEvent | None:
    stmt: Select = (
        select(FireEvent)
        .where(FireEvent.status.in_(ACTIVE_STATUSES))
        .order_by(desc(FireEvent.started_at), desc(FireEvent.id))
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_timeline(db: AsyncSession, event_id: str) -> list[EventTimeline]:
    await get_event_or_404(db, event_id)
    result = await db.execute(
        select(EventTimeline).where(EventTimeline.event_id == event_id).order_by(EventTimeline.created_at, EventTimeline.id)
    )
    return list(result.scalars().all())


async def close_event(db: AsyncSession, event_id: str) -> FireEvent:
    event = await get_event_or_404(db, event_id)
    event.status = "closed"
    event.closed_at = datetime.now(timezone.utc)
    await append_timeline(
        db,
        event_id=event.event_id,
        event_type="event.closed",
        status=event.status,
        title="Fire event closed",
        message="The active fire event has been closed.",
        payload=_event_public_payload(event),
        broadcast=True,
    )
    await db.commit()
    await db.refresh(event)
    await websocket_manager.broadcast_event(event.event_id, "event.closed", _event_public_payload(event))
    return event
