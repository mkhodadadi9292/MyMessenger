from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

POOL_RECYCLE_SECONDS = 1800
STATEMENT_TIMEOUT_MS = "15000"


def create_engine(
    database_url: str,
    pool_size: int = 10,
    max_overflow: int = 5,
    pool_timeout_seconds: int = 10,
) -> AsyncEngine:
    if database_url.startswith("sqlite"):
        engine = create_async_engine(database_url)

        @event.listens_for(engine.sync_engine, "connect")
        def _enable_sqlite_fks(dbapi_connection, connection_record) -> None:  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine
    return create_async_engine(
        database_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout_seconds,
        pool_recycle=POOL_RECYCLE_SECONDS,
        pool_pre_ping=True,
        connect_args={"server_settings": {"statement_timeout": STATEMENT_TIMEOUT_MS}},
    )


def create_engine_and_sessionmaker(
    database_url: str,
    pool_size: int = 10,
    max_overflow: int = 5,
    pool_timeout_seconds: int = 10,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_engine(database_url, pool_size, max_overflow, pool_timeout_seconds)
    return engine, async_sessionmaker(engine, expire_on_commit=False)
