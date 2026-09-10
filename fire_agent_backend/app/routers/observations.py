from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.observation import (
    EvidenceChainRead,
    FusionResultRead,
    ObservationEnvelope,
    ObservationRead,
    ObservationSimulationResult,
    TrustedFirePointRead,
)
from app.services.observation_service import (
    latest_fusion_result,
    latest_trusted_fire_point,
    list_evidence_chain,
    list_observations,
    simulate_observation_workflow,
)

router = APIRouter(prefix="/events/{event_id}", tags=["observations"])


@router.post("/observations/simulate", response_model=ObservationEnvelope, deprecated=True)
async def simulate_observations(event_id: str, db: AsyncSession = Depends(get_db)) -> ObservationEnvelope:
    """Legacy compatibility endpoint.

    This keeps stage-three acceptance reproducible, but the production direction is
    stage-four clock-driven generation where observations appear over time.
    """
    result = await simulate_observation_workflow(db, event_id)
    return ObservationEnvelope(
        data=ObservationSimulationResult(
            observations=[ObservationRead.model_validate(item) for item in result["observations"]],
            evidence_chain=[EvidenceChainRead.model_validate(item) for item in result["evidence_chain"]],
            fusion_result=FusionResultRead.model_validate(result["fusion_result"]),
            trusted_fire_point=TrustedFirePointRead.model_validate(result["trusted_fire_point"]),
        )
    )


@router.get("/observations", response_model=ObservationEnvelope)
async def observations(event_id: str, db: AsyncSession = Depends(get_db)) -> ObservationEnvelope:
    return ObservationEnvelope(data=[ObservationRead.model_validate(item) for item in await list_observations(db, event_id)])


@router.get("/evidence-chain", response_model=ObservationEnvelope)
async def evidence_chain(event_id: str, db: AsyncSession = Depends(get_db)) -> ObservationEnvelope:
    return ObservationEnvelope(data=[EvidenceChainRead.model_validate(item) for item in await list_evidence_chain(db, event_id)])


@router.get("/fusion", response_model=ObservationEnvelope)
async def fusion(event_id: str, db: AsyncSession = Depends(get_db)) -> ObservationEnvelope:
    item = await latest_fusion_result(db, event_id)
    return ObservationEnvelope(data=FusionResultRead.model_validate(item) if item else None)


@router.get("/trusted-fire-point", response_model=ObservationEnvelope)
async def trusted_fire_point(event_id: str, db: AsyncSession = Depends(get_db)) -> ObservationEnvelope:
    item = await latest_trusted_fire_point(db, event_id)
    return ObservationEnvelope(data=TrustedFirePointRead.model_validate(item) if item else None)
