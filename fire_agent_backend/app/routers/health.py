from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


def mask_database_url(url: str) -> str:
    if "@" not in url:
        return url
    prefix, suffix = url.rsplit("@", 1)
    scheme = prefix.split("://", 1)[0]
    return f"{scheme}://***@{suffix}"


@router.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"message": "Xinghuo Fire Agent Backend is running."}


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        ok=True,
        app_name=settings.app_name,
        app_version=settings.app_version,
        environment=settings.environment,
        database_url=mask_database_url(settings.resolved_database_url),
        data_dir=str(settings.resolved_data_dir),
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
    )
