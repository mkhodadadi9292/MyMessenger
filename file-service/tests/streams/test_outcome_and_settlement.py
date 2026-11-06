from datetime import datetime

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from file_service.domain.upload_session import UploadSession, UploadStatus
from file_service.infrastructure.db.base import Base
from file_service.infrastructure.db.repositories import SqlUploadSessionRepository
from file_service.infrastructure.streams import (
    RedisStreamSettlement,
    StreamConsumer,
    dead_letter_stream,
)
from file_service.infrastructure.workers import build_outcome_handler

pytestmark = pytest.mark.redis

COMPLETED = "upload.completed"
OUTCOME = "upload.outcome"
BACKEND = "messenger-backend"
FILE_SERVICE = "file-service"


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def add_completed(session_factory, upload_id: str) -> None:
    now = datetime(2026, 1, 1)
    async with session_factory() as session:
        await SqlUploadSessionRepository(session).add(
            UploadSession(
                upload_id=upload_id,
                user_id=1,
                mime_type="image/png",
                size_bytes=1,
                sha256="0" * 64,
                chunk_size=1,
                total_chunks=1,
                status=UploadStatus.COMPLETED,
                ticket="t",
                created_at=now,
                last_activity_at=now,
                file_path="artifacts/x.png",
            )
        )
        await session.commit()


async def status_of(session_factory, upload_id: str) -> UploadStatus:
    async with session_factory() as session:
        return (await SqlUploadSessionRepository(session).get(upload_id)).status


def outcome_consumer(redis: Redis, session_factory) -> StreamConsumer:
    return StreamConsumer(
        redis, OUTCOME, FILE_SERVICE, build_outcome_handler(session_factory),
        consumer="fs", claim_min_idle_ms=0, block_ms=50,
    )


@pytest.mark.parametrize(
    ("event_type", "expected"),
    [("upload.attached", UploadStatus.ATTACHED), ("upload.rejected", UploadStatus.REJECTED)],
)
async def test_outcome_event_updates_session(
    real_redis: Redis, session_factory, event_type: str, expected: UploadStatus
) -> None:
    await add_completed(session_factory, "a" * 32)
    worker = outcome_consumer(real_redis, session_factory)
    await worker.ensure_group()
    await real_redis.xadd(OUTCOME, {"type": event_type, "upload_id": "a" * 32})
    await real_redis.xadd(OUTCOME, {"type": event_type, "upload_id": "a" * 32})
    await worker.process_new()
    assert await status_of(session_factory, "a" * 32) is expected
    assert (await real_redis.xpending(OUTCOME, FILE_SERVICE))["pending"] == 0


async def test_unknown_outcome_type_is_dead_lettered(real_redis: Redis, session_factory) -> None:
    worker = outcome_consumer(real_redis, session_factory)
    await worker.ensure_group()
    await real_redis.xadd(OUTCOME, {"type": "upload.weird", "upload_id": "a" * 32})
    await worker.process_new()
    assert await real_redis.xlen(dead_letter_stream(OUTCOME)) == 1


def settlement(redis: Redis) -> RedisStreamSettlement:
    return RedisStreamSettlement(redis, COMPLETED, BACKEND, OUTCOME, FILE_SERVICE)


async def setup_groups(redis: Redis) -> str:
    await redis.xgroup_create(COMPLETED, BACKEND, id="0", mkstream=True)
    await redis.xgroup_create(OUTCOME, FILE_SERVICE, id="0", mkstream=True)
    return await redis.xadd(COMPLETED, {"upload_id": "u1"})


async def test_not_settled_before_backend_reads_the_event(real_redis: Redis) -> None:
    event_id = await setup_groups(real_redis)
    assert not await settlement(real_redis).is_settled("u1", event_id)


async def test_not_settled_while_backend_has_it_pending(real_redis: Redis) -> None:
    event_id = await setup_groups(real_redis)
    await real_redis.xreadgroup(BACKEND, "b", {COMPLETED: ">"})
    assert not await settlement(real_redis).is_settled("u1", event_id)


async def test_not_settled_while_an_outcome_is_unprocessed(real_redis: Redis) -> None:
    event_id = await setup_groups(real_redis)
    await real_redis.xreadgroup(BACKEND, "b", {COMPLETED: ">"})
    await real_redis.xack(COMPLETED, BACKEND, event_id)
    await real_redis.xadd(OUTCOME, {"type": "upload.attached", "upload_id": "u1"})
    assert not await settlement(real_redis).is_settled("u1", event_id)


async def test_settled_when_backend_acked_and_outcomes_drained(real_redis: Redis) -> None:
    event_id = await setup_groups(real_redis)
    await real_redis.xreadgroup(BACKEND, "b", {COMPLETED: ">"})
    await real_redis.xack(COMPLETED, BACKEND, event_id)
    assert await settlement(real_redis).is_settled("u1", event_id)


@pytest.mark.parametrize("stream", [COMPLETED, OUTCOME])
async def test_not_settled_when_upload_is_in_dead_letters(real_redis: Redis, stream: str) -> None:
    event_id = await setup_groups(real_redis)
    await real_redis.xreadgroup(BACKEND, "b", {COMPLETED: ">"})
    await real_redis.xack(COMPLETED, BACKEND, event_id)
    await real_redis.xadd(dead_letter_stream(stream), {"upload_id": "u1"})
    assert not await settlement(real_redis).is_settled("u1", event_id)


async def test_settled_after_outcomes_were_applied_and_trimmed(real_redis: Redis) -> None:
    event_id = await setup_groups(real_redis)
    await real_redis.xreadgroup(BACKEND, "b", {COMPLETED: ">"})
    await real_redis.xack(COMPLETED, BACKEND, event_id)
    outcome_id = await real_redis.xadd(OUTCOME, {"type": "upload.attached", "upload_id": "u0"})
    await real_redis.xreadgroup(FILE_SERVICE, "f", {OUTCOME: ">"})
    await real_redis.xack(OUTCOME, FILE_SERVICE, outcome_id)
    await real_redis.xdel(OUTCOME, outcome_id)
    assert await settlement(real_redis).is_settled("u1", event_id)
    await real_redis.xadd(OUTCOME, {"type": "upload.attached", "upload_id": "u2"})
    assert not await settlement(real_redis).is_settled("u1", event_id)
