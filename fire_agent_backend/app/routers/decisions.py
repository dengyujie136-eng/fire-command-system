from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.session import get_db
from app.schemas.decision import AgentPacketRead, DecisionEnvelope, DecisionRunPayload, DecisionRunRead, DecisionRunRequest
from app.services.decision_service import create_decision_run, decision_packets, latest_decision_run

router = APIRouter(tags=["decisions"])


def _payload(data: dict) -> DecisionRunPayload:
    run = data["run"]
    packages = data.get("packages", {})
    return DecisionRunPayload(
        run=DecisionRunRead.model_validate(run),
        packets=[AgentPacketRead.model_validate(item) for item in data.get("packets", [])],
        packages=packages,
        recommended_plan=run.recommended_plan,
        input_summary=run.input_summary,
        warnings=run.warnings,
    )


@router.post("/events/{event_id}/decision-runs", response_model=DecisionEnvelope)
async def create(event_id: str, request: DecisionRunRequest, db: AsyncSession = Depends(get_db)) -> DecisionEnvelope:
    return DecisionEnvelope(data=_payload(await create_decision_run(db, event_id, request)))


@router.get("/events/{event_id}/decision-runs/latest", response_model=DecisionEnvelope)
async def latest(event_id: str, db: AsyncSession = Depends(get_db)) -> DecisionEnvelope:
    data = await latest_decision_run(db, event_id)
    return DecisionEnvelope(data=_payload(data) if data else None)


@router.get("/decision-runs/{decision_run_id}/packets", response_model=DecisionEnvelope)
async def packets(decision_run_id: str, db: AsyncSession = Depends(get_db)) -> DecisionEnvelope:
    items = await decision_packets(db, decision_run_id)
    if not items:
        raise AppError(f"Decision run not found or has no packets: {decision_run_id}", code="decision_run_not_found", status_code=404)
    return DecisionEnvelope(data=[AgentPacketRead.model_validate(item) for item in items])
