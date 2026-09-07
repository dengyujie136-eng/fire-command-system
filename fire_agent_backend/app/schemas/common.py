from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ApiResponse(BaseModel):
    ok: bool = True
    data: Any | None = None
    message: str | None = None


class HealthResponse(BaseModel):
    ok: bool
    app_name: str
    app_version: str
    environment: str
    database_url: str
    data_dir: str
    llm_provider: str
    llm_model: str


class SystemStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ok: bool
    service: str
    version: str
    timestamp: datetime
    websocket_endpoint: str
    database_ready: bool
