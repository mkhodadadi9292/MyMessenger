import asyncio
import logging
from collections.abc import Awaitable, Callable

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from file_service.application.outcome_service import OutcomeService, UnknownOutcomeError
from file_service.config import Settings
from file_service.infrastructure.composition import build_outbox_relay, build_outcome_service
from file_service.infrastructure.streams import PermanentEventError, StreamConsumer

logger = logging.getLogger("file_service.workers")


def build_outcome_handler(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[dict[str, str]], Awaitable[None]]:
    async def handle(fields: dict[str, str]) -> None:
        upload_id = fields.get("upload_id")
        outcome_type = fields.get("type")
        if not upload_id or not outcome_type:
            raise PermanentEventError("outcome event is missing upload_id or type")
        async with session_factory() as session:
            service: OutcomeService = build_outcome_service(session)
            try:
                await service.apply(outcome_type, upload_id, fields.get("reason"))
            except UnknownOutcomeError as exc:
                raise PermanentEventError(f"unknown outcome type {exc}") from exc

    return handle


def build_outcome_consumer(
    redis: Redis, session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> StreamConsumer:
    return StreamConsumer(
        redis,
        settings.outcome_stream,
        settings.outcome_group,
        build_outcome_handler(session_factory),
        max_deliveries=settings.stream_max_deliveries,
        claim_min_idle_ms=settings.stream_claim_min_idle_ms,
        claim_interval_seconds=settings.stream_claim_interval_seconds,
        block_ms=settings.stream_block_ms,
    )


async def run_outbox_relay(
    redis: Redis,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    stop: asyncio.Event,
) -> None:
    while not stop.is_set():
        try:
            async with session_factory() as session:
                await build_outbox_relay(session, redis, settings).relay_pending()
        except Exception:
            logger.exception("outbox relay pass failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.outbox_relay_interval_seconds)
        except TimeoutError:
            pass
