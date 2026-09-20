from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api.errors import register_error_handlers
from app.api.routers import health
from app.config import Settings, get_settings
from app.infrastructure.db.session import create_engine_and_sessionmaker


def _ensure_sqlite_parent(database_url: str) -> None:
    if database_url.startswith("sqlite"):
        db_path = database_url.split("///", 1)[-1]
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    settings.media_root.mkdir(parents=True, exist_ok=True)
    _ensure_sqlite_parent(settings.database_url)

    engine, session_factory = create_engine_and_sessionmaker(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        await engine.dispose()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory

    app.include_router(health.router)
    register_error_handlers(app)

    return app
