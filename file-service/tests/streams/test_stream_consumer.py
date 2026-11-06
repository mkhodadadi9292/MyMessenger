import asyncio

import pytest
from redis.asyncio import Redis

from file_service.infrastructure.streams import (
    PermanentEventError,
    StreamConsumer,
    dead_letter_stream,
)

pytestmark = pytest.mark.redis

STREAM = "test.events"
GROUP = "test-group"


def consumer(redis: Redis, handler, name: str = "c1", **overrides) -> StreamConsumer:
    options = {"max_deliveries": 3, "claim_min_idle_ms": 0, "block_ms": 50}
    options.update(overrides)
    return StreamConsumer(redis, STREAM, GROUP, handler, consumer=name, **options)


async def pending_count(redis: Redis) -> int:
    return (await redis.xpending(STREAM, GROUP))["pending"]


async def test_published_event_is_consumed_and_acked(real_redis: Redis) -> None:
    seen: list[dict] = []

    async def handle(fields: dict) -> None:
        seen.append(fields)

    worker = consumer(real_redis, handle)
    await worker.ensure_group()
    await real_redis.xadd(STREAM, {"upload_id": "a"})
    assert await worker.process_new() == 1
    assert seen == [{"upload_id": "a"}]
    assert await pending_count(real_redis) == 0


async def test_group_created_late_still_sees_earlier_events(real_redis: Redis) -> None:
    await real_redis.xadd(STREAM, {"upload_id": "early"})
    seen: list[str] = []

    async def handle(fields: dict) -> None:
        seen.append(fields["upload_id"])

    worker = consumer(real_redis, handle)
    await worker.ensure_group()
    await worker.process_new()
    assert seen == ["early"]


async def test_failed_handler_leaves_event_pending(real_redis: Redis) -> None:
    async def handle(fields: dict) -> None:
        raise RuntimeError("database commit failed")

    worker = consumer(real_redis, handle)
    await worker.ensure_group()
    await real_redis.xadd(STREAM, {"upload_id": "a"})
    await worker.process_new()
    assert await pending_count(real_redis) == 1
    assert await real_redis.xlen(dead_letter_stream(STREAM)) == 0


async def test_stale_event_is_redelivered_to_another_consumer(real_redis: Redis) -> None:
    async def crash(fields: dict) -> None:
        raise RuntimeError("consumer died")

    seen: list[str] = []

    async def handle(fields: dict) -> None:
        seen.append(fields["upload_id"])

    first = consumer(real_redis, crash, name="first")
    await first.ensure_group()
    await real_redis.xadd(STREAM, {"upload_id": "a"})
    await first.process_new()
    second = consumer(real_redis, handle, name="second")
    assert await second.process_stale() == 1
    assert seen == ["a"]
    assert await pending_count(real_redis) == 0


async def test_event_goes_to_dead_letters_after_max_deliveries(real_redis: Redis) -> None:
    attempts = 0

    async def handle(fields: dict) -> None:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("always failing")

    worker = consumer(real_redis, handle, max_deliveries=2)
    await worker.ensure_group()
    entry_id = await real_redis.xadd(STREAM, {"upload_id": "a"})
    await worker.process_new()
    await worker.process_stale()
    await worker.process_stale()
    assert attempts == 2
    assert await pending_count(real_redis) == 0
    dead = await real_redis.xrange(dead_letter_stream(STREAM))
    assert len(dead) == 1
    assert dead[0][1]["upload_id"] == "a"
    assert dead[0][1]["source_id"] == entry_id
    assert dead[0][1]["deliveries"] == "3"


async def test_keep_pending_check_prevents_dead_lettering(real_redis: Redis) -> None:
    async def handle(fields: dict) -> None:
        raise RuntimeError("outcome publish failed")

    async def keep(fields: dict) -> bool:
        return True

    worker = consumer(real_redis, handle, max_deliveries=1, keep_pending=keep)
    await worker.ensure_group()
    await real_redis.xadd(STREAM, {"upload_id": "a"})
    await worker.process_new()
    for _ in range(3):
        await worker.process_stale()
    assert await pending_count(real_redis) == 1
    assert await real_redis.xlen(dead_letter_stream(STREAM)) == 0


async def test_permanent_error_dead_letters_immediately(real_redis: Redis) -> None:
    async def handle(fields: dict) -> None:
        raise PermanentEventError("bad schema")

    worker = consumer(real_redis, handle)
    await worker.ensure_group()
    await real_redis.xadd(STREAM, {"junk": "1"})
    await worker.process_new()
    assert await pending_count(real_redis) == 0
    dead = await real_redis.xrange(dead_letter_stream(STREAM))
    assert dead[0][1]["error"] == "bad schema"


async def test_run_loop_stops_cleanly(real_redis: Redis) -> None:
    seen: list[str] = []

    async def handle(fields: dict) -> None:
        seen.append(fields["upload_id"])

    worker = consumer(real_redis, handle)
    stop = asyncio.Event()
    task = asyncio.create_task(worker.run(stop))
    await real_redis.xadd(STREAM, {"upload_id": "a"})
    for _ in range(50):
        if seen:
            break
        await asyncio.sleep(0.05)
    stop.set()
    await asyncio.wait_for(task, timeout=2)
    assert seen == ["a"]
