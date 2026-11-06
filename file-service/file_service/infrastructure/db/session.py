from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from file_service.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    if settings.database_url.startswith("sqlite"):
        return create_async_engine(settings.database_url)
    return create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
        pool_recycle=1800,
        pool_pre_ping=True,
        connect_args={"server_settings": {"statement_timeout": "15000"}},
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
