import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis

from file_service.api.errors import register_error_handlers
from file_service.api.routers import health, internal, uploads
from file_service.config import Settings, get_settings
from file_service.infrastructure.db.session import create_engine, create_session_factory
from file_service.infrastructure.workers import build_outcome_consumer, run_outbox_relay

WORKER_SHUTDOWN_TIMEOUT_SECONDS = 10


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s"
    )
    settings.media_root.mkdir(parents=True, exist_ok=True)
    settings.chunks_root.mkdir(parents=True, exist_ok=True)
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    redis = (
        Redis.from_url(settings.redis_url, decode_responses=True) if settings.redis_url else None
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        stop = asyncio.Event()
        tasks: list[asyncio.Task] = []
        if app.state.redis is not None and settings.workers_enabled:
            consumer = build_outcome_consumer(app.state.redis, app.state.session_factory, settings)
            tasks.append(asyncio.create_task(consumer.run(stop)))
            tasks.append(
                asyncio.create_task(
                    run_outbox_relay(app.state.redis, app.state.session_factory, settings, stop)
                )
            )
        try:
            yield
        finally:
            stop.set()
            if tasks:
                _, still_running = await asyncio.wait(
                    tasks, timeout=WORKER_SHUTDOWN_TIMEOUT_SECONDS
                )
                for task in still_running:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
            if app.state.redis is not None:
                await app.state.redis.aclose()
            await app.state.engine.dispose()

    app = FastAPI(title=settings.app_name, lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.redis = redis
    app.include_router(health.router)
    app.include_router(uploads.router)
    app.include_router(internal.router)
    register_error_handlers(app)
    return app
