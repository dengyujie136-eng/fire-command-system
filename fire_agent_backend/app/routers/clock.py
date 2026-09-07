from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.clock import ClockEnvelope, ClockStartRequest, ClockStatePayload, ClockStepRequest
from app.schemas.observation import FusionResultRead, ObservationRead, TrustedFirePointRead
from app.schemas.clock import EnvironmentSnapshotRead, SimulationClockRead
from app.services.clock_service import clock_state, pause_clock, reset_clock, resume_clock, start_clock, step_clock

router = APIRouter(prefix="/events/{event_id}/clock", tags=["clock"])


def _payload(data: dict) -> ClockStatePayload:
    return ClockStatePayload(
        clock=SimulationClockRead.model_validate(data["clock"]),
        environment=EnvironmentSnapshotRead.model_validate(data["environment"]) if data.get("environment") else None,
        observations=[ObservationRead.model_validate(item) for item in data.get("observations", [])],
        fusion_result=FusionResultRead.model_validate(data["fusion_result"]) if data.get("fusion_result") else None,
        trusted_fire_point=TrustedFirePointRead.model_validate(data["trusted_fire_point"]) if data.get("trusted_fire_point") else None,
    )


@router.get("", response_model=ClockEnvelope)
async def get_clock(event_id: str, db: AsyncSession = Depends(get_db)) -> ClockEnvelope:
    return ClockEnvelope(data=_payload(await clock_state(db, event_id)))


@router.post("/start", response_model=ClockEnvelope)
async def start(event_id: str, request: ClockStartRequest, db: AsyncSession = Depends(get_db)) -> ClockEnvelope:
    return ClockEnvelope(data=_payload(await start_clock(db, event_id, request)))


@router.post("/pause", response_model=ClockEnvelope)
async def pause(event_id: str, db: AsyncSession = Depends(get_db)) -> ClockEnvelope:
    return ClockEnvelope(data=_payload(await pause_clock(db, event_id)))


@router.post("/resume", response_model=ClockEnvelope)
async def resume(event_id: str, db: AsyncSession = Depends(get_db)) -> ClockEnvelope:
    return ClockEnvelope(data=_payload(await resume_clock(db, event_id)))


@router.post("/reset", response_model=ClockEnvelope)
async def reset(event_id: str, db: AsyncSession = Depends(get_db)) -> ClockEnvelope:
    return ClockEnvelope(data=_payload(await reset_clock(db, event_id)))


@router.post("/step", response_model=ClockEnvelope)
async def step(event_id: str, request: ClockStepRequest | None = None, db: AsyncSession = Depends(get_db)) -> ClockEnvelope:
    return ClockEnvelope(data=_payload(await step_clock(db, event_id, request)))
