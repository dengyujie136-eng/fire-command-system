from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ReportCreateRequest(BaseModel):
    include_recalculation: bool = True
    format: str = "markdown"


class DecisionReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_id: str
    event_id: str
    decision_run_id: str
    recommendation_package_id: str
    recalculation_id: str
    title: str
    status: str
    format: str
    summary: str
    sections: dict[str, Any]
    content_markdown: str
    generated_by: str
    created_at: datetime
    updated_at: datetime


class ReportEnvelope(BaseModel):
    ok: bool = True
    data: Any
