from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.report import DecisionReportRead, ReportCreateRequest, ReportEnvelope
from app.services.report_service import generate_report, get_report, latest_report, render_report_pdf

router = APIRouter(tags=["reports"])


@router.post("/events/{event_id}/reports", response_model=ReportEnvelope)
async def create(event_id: str, request: ReportCreateRequest, db: AsyncSession = Depends(get_db)) -> ReportEnvelope:
    return ReportEnvelope(data=DecisionReportRead.model_validate(await generate_report(db, event_id, request)))


@router.get("/events/{event_id}/reports/latest", response_model=ReportEnvelope)
async def latest(event_id: str, db: AsyncSession = Depends(get_db)) -> ReportEnvelope:
    report = await latest_report(db, event_id)
    return ReportEnvelope(data=DecisionReportRead.model_validate(report) if report else None)


@router.get("/reports/{report_id}", response_model=ReportEnvelope)
async def detail(report_id: str, db: AsyncSession = Depends(get_db)) -> ReportEnvelope:
    return ReportEnvelope(data=DecisionReportRead.model_validate(await get_report(db, report_id)))


@router.get("/reports/{report_id}/download")
async def download(report_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    report = await get_report(db, report_id)
    filename = f"{report.report_id}.md"
    return Response(
        content=report.content_markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports/{report_id}/download.pdf")
async def download_pdf(report_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    report = await get_report(db, report_id)
    filename = f"{report.report_id}.pdf"
    return Response(
        content=render_report_pdf(report),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
