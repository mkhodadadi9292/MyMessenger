import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from redis.asyncio import Redis

from app.api.errors import register_error_handlers
from app.api.routers import (
    artifacts,
    auth,
    blocked,
    chats,
    contacts,
    health,
    invites,
    messages,
    uploads,
    users,
    ws,
)
from app.api.upload_events import UploadCompletedHandler
from app.config import Settings, get_settings
from app.infrastructure.auth.otp import LogOtpSender
from app.infrastructure.db.session import create_engine_and_sessionmaker
from app.infrastructure.realtime import ConnectionManager
from app.infrastructure.streams import RedisUploadOutcomePublisher, StreamConsumer

API_PREFIX = "/api/v1"
CONSUMER_SHUTDOWN_TIMEOUT_SECONDS = 10


def _ensure_sqlite_parent(database_url: str) -> None:
    if database_url.startswith("sqlite"):
        db_path = database_url.split("///", 1)[-1]
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)


@contextlib.asynccontextmanager
async def _upload_consumer(app: FastAPI, settings: Settings) -> AsyncIterator[None]:
    if not settings.redis_url or not settings.upload_consumer_enabled:
        yield
        return
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    consumer_engine, consumer_sessions = create_engine_and_sessionmaker(
        settings.database_url,
        settings.consumer_db_pool_size,
        0,
        settings.db_pool_timeout_seconds,
    )
    handler = UploadCompletedHandler(
        consumer_sessions,
        app.state.realtime,
        RedisUploadOutcomePublisher(redis, settings.outcome_stream, settings.stream_maxlen),
        settings,
    )
    consumer = StreamConsumer(
        redis,
        settings.completed_stream,
        settings.upload_consumer_group,
        handler,
        max_deliveries=settings.stream_max_deliveries,
        claim_min_idle_ms=settings.stream_claim_min_idle_ms,
        claim_interval_seconds=settings.stream_claim_interval_seconds,
        block_ms=settings.stream_block_ms,
        keep_pending=handler.has_attached_artifact,
    )
    stop = asyncio.Event()
    task = asyncio.create_task(consumer.run(stop))
    try:
        yield
    finally:
        stop.set()
        done, _ = await asyncio.wait({task}, timeout=CONSUMER_SHUTDOWN_TIMEOUT_SECONDS)
        if not done:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await redis.aclose()
        await consumer_engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    if settings.upload_ticket_secret == settings.jwt_secret:
        raise RuntimeError("UPLOAD_TICKET_SECRET must differ from JWT_SECRET")
    # Root handler so app loggers (e.g. OTP delivery) reach the console;
    # uvicorn's own logging config only wires up its own loggers.
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s"
    )
    settings.media_root.mkdir(parents=True, exist_ok=True)
    _ensure_sqlite_parent(settings.database_url)

    engine, session_factory = create_engine_and_sessionmaker(
        settings.database_url,
        settings.db_pool_size,
        settings.db_max_overflow,
        settings.db_pool_timeout_seconds,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with _upload_consumer(app, settings):
            yield
        await app.state.engine.dispose()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.otp_sender = LogOtpSender()
    app.state.realtime = ConnectionManager()

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
        uploads.router,
    ):
        app.include_router(router, prefix=API_PREFIX)
    app.include_router(ws.router)
    register_error_handlers(app)

    return app
