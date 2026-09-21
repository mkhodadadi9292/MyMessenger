import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.errors import register_error_handlers
from app.api.routers import artifacts, auth, blocked, chats, contacts, health, invites, messages, users
from app.config import Settings, get_settings
from app.infrastructure.auth.otp import LogOtpSender
from app.infrastructure.db.session import create_engine_and_sessionmaker

API_PREFIX = "/api/v1"


def _ensure_sqlite_parent(database_url: str) -> None:
    if database_url.startswith("sqlite"):
        db_path = database_url.split("///", 1)[-1]
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    # Root handler so app loggers (e.g. OTP delivery) reach the console;
    # uvicorn's own logging config only wires up its own loggers.
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s"
    )
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
    app.state.otp_sender = LogOtpSender()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    # Dev convenience; Nginx serves this tree in production.
    app.mount("/media", StaticFiles(directory=settings.media_root), name="media")
    for router in (
        auth.router,
        users.router,
        contacts.router,
        blocked.router,
        chats.router,
        invites.router,
        messages.router,
        artifacts.router,
    ):
        app.include_router(router, prefix=API_PREFIX)
    register_error_handlers(app)

    return app
