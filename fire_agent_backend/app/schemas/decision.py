from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class DecisionRunRequest(BaseModel):
    force_provider: str | None = None
    include_report: bool = True


class DecisionRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decision_run_id: str
    event_id: str
    scenario_id: str
    status: str
    provider: str
    model: str
    confidence: float
    recommended_plan: dict[str, Any]
    input_summary: dict[str, Any]
    warnings: list[str]
    raw_llm_output: str
    created_at: datetime


class AgentPacketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    packet_id: str
    decision_run_id: str
    event_id: str
    packet_type: str
    title: str
    content: dict[str, Any]
    created_at: datetime


class DecisionRunPayload(BaseModel):
    run: DecisionRunRead
    packets: list[AgentPacketRead]
    packages: dict[str, Any]
    recommended_plan: dict[str, Any]
    input_summary: dict[str, Any]
    warnings: list[str]


class DecisionEnvelope(BaseModel):
    ok: bool = True
    data: Any
