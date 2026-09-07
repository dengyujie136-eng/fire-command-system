from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.base import Base

settings = get_settings()
settings.resolved_data_dir.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(
    settings.resolved_database_url,
    echo=settings.database_echo,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    from app.models import event as _event  # noqa: F401
    from app.models import decision as _decision  # noqa: F401
    from app.models import observation as _observation  # noqa: F401
    from app.models import recalculation as _recalculation  # noqa: F401
    from app.models import recommendation as _recommendation  # noqa: F401
    from app.models import report as _report  # noqa: F401
    from app.models import scenario as _scenario  # noqa: F401
    from app.models import spread as _spread  # noqa: F401
    from app.models import system as _system  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
