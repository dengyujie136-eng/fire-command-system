from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.workflow import (
    CommanderReviewRequest,
    HumanVerificationRequest,
    ScenarioConfirmRequest,
    ScenarioGenerateRequest,
    WorkflowCreateRequest,
    WorkflowEnvelope,
    WorkflowSpreadRerunRequest,
    VerificationProgressRequest,
)
from app.services.workflow_runtime_service import (
    _run_or_404,
    confirm_scenario,
    create_workflow,
    data_readiness,
    execute_analysis,
    execute_downstream,
    generate_scenario,
    human_verify,
    latest_workflow,
    list_events,
    prepare_workflow,
    request_spread_rerun,
    resume_workflow,
    review_commander,
    execute_spread_rerun,
    workflow_payload,
    update_verification_progress,
)


router = APIRouter(tags=["workflow-runtime"])


@router.get("/workflow/events", response_model=WorkflowEnvelope)
async def events(db: AsyncSession = Depends(get_db)) -> WorkflowEnvelope:
    return WorkflowEnvelope(data=await list_events(db))


@router.get("/events/{event_id}/workflow-readiness", response_model=WorkflowEnvelope)
async def readiness(event_id: str, db: AsyncSession = Depends(get_db)) -> WorkflowEnvelope:
    return WorkflowEnvelope(data=await data_readiness(db, event_id))


@router.post("/events/{event_id}/workflow-runs", response_model=WorkflowEnvelope, status_code=202)
async def create(
    event_id: str,
    request: WorkflowCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> WorkflowEnvelope:
    run = await create_workflow(db, event_id, request)
    background_tasks.add_task(prepare_workflow, run.workflow_run_id)
    return WorkflowEnvelope(data=await workflow_payload(db, run))


@router.get("/events/{event_id}/workflow-runs/latest", response_model=WorkflowEnvelope)
async def latest(event_id: str, db: AsyncSession = Depends(get_db)) -> WorkflowEnvelope:
    run = await latest_workflow(db, event_id)
    return WorkflowEnvelope(data=await workflow_payload(db, run) if run else None)


@router.get("/workflow-runs/{workflow_run_id}", response_model=WorkflowEnvelope)
async def detail(workflow_run_id: str, db: AsyncSession = Depends(get_db)) -> WorkflowEnvelope:
    run = await _run_or_404(db, workflow_run_id)
    return WorkflowEnvelope(data=await workflow_payload(db, run))


@router.post("/workflow-runs/{workflow_run_id}/spread-reruns", response_model=WorkflowEnvelope, status_code=202)
async def spread_rerun(
    workflow_run_id: str,
    request: WorkflowSpreadRerunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> WorkflowEnvelope:
    run = await request_spread_rerun(db, workflow_run_id, request)
    background_tasks.add_task(execute_spread_rerun, run.workflow_run_id, request)
    return WorkflowEnvelope(data=await workflow_payload(db, run))


@router.post("/workflow-runs/{workflow_run_id}/verification", response_model=WorkflowEnvelope)
async def verify(
    workflow_run_id: str,
    request: HumanVerificationRequest,
    db: AsyncSession = Depends(get_db),
) -> WorkflowEnvelope:
    run = await human_verify(db, workflow_run_id, request)
    return WorkflowEnvelope(data=await workflow_payload(db, run))


@router.post("/workflow-runs/{workflow_run_id}/verification-progress", response_model=WorkflowEnvelope)
async def verification_progress(
    workflow_run_id: str,
    request: VerificationProgressRequest,
    db: AsyncSession = Depends(get_db),
) -> WorkflowEnvelope:
    run = await update_verification_progress(db, workflow_run_id, request)
    return WorkflowEnvelope(data=await workflow_payload(db, run))


@router.post("/workflow-runs/{workflow_run_id}/scenario", response_model=WorkflowEnvelope)
async def scenario(
    workflow_run_id: str,
    request: ScenarioGenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> WorkflowEnvelope:
    await generate_scenario(db, workflow_run_id, request)
    run = await _run_or_404(db, workflow_run_id)
    return WorkflowEnvelope(data=await workflow_payload(db, run))


@router.post("/workflow-runs/{workflow_run_id}/scenario/confirm", response_model=WorkflowEnvelope)
async def scenario_confirm(
    workflow_run_id: str,
    request: ScenarioConfirmRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> WorkflowEnvelope:
    await confirm_scenario(db, workflow_run_id, request)
    if request.run_downstream:
        background_tasks.add_task(execute_downstream, workflow_run_id)
    run = await _run_or_404(db, workflow_run_id)
    return WorkflowEnvelope(data=await workflow_payload(db, run))


@router.post("/workflow-runs/{workflow_run_id}/commander/review", response_model=WorkflowEnvelope)
async def commander_review(
    workflow_run_id: str,
    request: CommanderReviewRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> WorkflowEnvelope:
    run = await review_commander(db, workflow_run_id, request)
    if request.action == "regenerate":
        background_tasks.add_task(execute_downstream, workflow_run_id)
    return WorkflowEnvelope(data=await workflow_payload(db, run))


@router.post("/workflow-runs/{workflow_run_id}/resume", response_model=WorkflowEnvelope, status_code=202)
async def resume(
    workflow_run_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> WorkflowEnvelope:
    run = await _run_or_404(db, workflow_run_id)
    background_tasks.add_task(resume_workflow, workflow_run_id)
    return WorkflowEnvelope(data=await workflow_payload(db, run))
