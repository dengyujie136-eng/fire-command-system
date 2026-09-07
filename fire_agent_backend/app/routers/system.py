from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.schemas.common import SystemStatusResponse
from app.services.websocket_manager import websocket_manager

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status", response_model=SystemStatusResponse)
async def system_status() -> SystemStatusResponse:
    settings = get_settings()
    database_ready = False
    postgis_ready = False
    database_backend = "unknown"
    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT 1"))
        database_ready = True
        bind = session.get_bind()
        database_backend = bind.dialect.name
        if database_backend == "postgresql":
            result = await session.execute(text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'postgis')"))
            postgis_ready = bool(result.scalar())
    return SystemStatusResponse(
        ok=True,
        service=settings.app_name,
        version=settings.app_version,
        timestamp=datetime.now(timezone.utc),
        websocket_endpoint="/ws/system",
        database_ready=database_ready,
        database_backend=database_backend,
        postgis_ready=postgis_ready,
    )


@router.get("/connections")
async def websocket_connections() -> dict:
    return {
        "ok": True,
        "data": {
            "total": websocket_manager.connection_count(),
            "system": websocket_manager.connection_count("system"),
        },
    }
