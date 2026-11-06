import pytest
from redis.asyncio import Redis
from sqlalchemy import func, select

from app.api.upload_events import UploadCompletedHandler
from app.infrastructure.db.models import ArtifactModel, MessageModel
from app.infrastructure.streams import (
    RedisUploadOutcomePublisher,
    StreamConsumer,
    dead_letter_stream,
)
from tests.helpers import API_V1, auth_headers
from tests.uploads import completed_event, store_like_file_service, ticket_for

pytestmark = pytest.mark.redis

COMPLETED = "upload.completed"
OUTCOME = "upload.outcome"
GROUP = "messenger-backend"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


class FailingCommitSessions:
    def __init__(self, factory, failures: int) -> None:
        self._factory = factory
        self.failures = failures

    def __call__(self):
        session = self._factory()
        if self.failures > 0:
            self.failures -= 1

            async def broken_commit() -> None:
                raise ConnectionError("database went away during commit")

            session.commit = broken_commit
        return session


class UnreachableOutcomeStream(RedisUploadOutcomePublisher):
    async def publish_attached(self, upload_id: str, message_id: int, artifact_id: int) -> None:
        raise ConnectionError("redis write failed")


def consumer_for(
    app, redis: Redis, sessions=None, max_deliveries: int = 3, publisher=None
) -> StreamConsumer:
    handler = UploadCompletedHandler(
        sessions or app.state.session_factory,
        app.state.realtime,
        publisher or RedisUploadOutcomePublisher(redis, OUTCOME, 1000),
        app.state.settings,
    )
    return StreamConsumer(
        redis,
        COMPLETED,
        GROUP,
        handler,
        consumer="backend-test",
        max_deliveries=max_deliveries,
        claim_min_idle_ms=0,
        block_ms=50,
        keep_pending=handler.has_attached_artifact,
    )


async def counts(app) -> tuple[int, int]:
    async with app.state.session_factory() as session:
        return (
            await session.scalar(select(func.count()).select_from(MessageModel)),
            await session.scalar(select(func.count()).select_from(ArtifactModel)),
        )


async def pending(redis: Redis) -> int:
    return (await redis.xpending(COMPLETED, GROUP))["pending"]


async def publish_upload(app, client, redis: Redis, user_factory) -> dict:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat = await client.post(
        f"{API_V1}/chats/private",
        json={"user_id": alice["user"]["id"]},
        headers=auth_headers(bob["access_token"]),
    )
    upload = await ticket_for(
        client, alice, chat.json()["id"], "pic.png", PNG, "image/png", "image"
    )
    event = completed_event(upload, store_like_file_service(app, PNG, "image/png"))
    await redis.xadd(COMPLETED, event)
    return event


async def test_completed_event_is_attached_acked_and_answered(
    app, client, real_redis, user_factory
) -> None:
    consumer = consumer_for(app, real_redis)
    await consumer.ensure_group()
    event = await publish_upload(app, client, real_redis, user_factory)
    await consumer.process_new()
    assert await counts(app) == (1, 1)
    assert await pending(real_redis) == 0
    [(_, outcome)] = await real_redis.xrange(OUTCOME)
    assert outcome["type"] == "upload.attached"
    assert outcome["upload_id"] == event["upload_id"]
    assert outcome["schema_version"] == "1"


async def test_no_ack_and_no_outcome_when_commit_fails(
    app, client, real_redis, user_factory
) -> None:
    sessions = FailingCommitSessions(app.state.session_factory, failures=1)
    consumer = consumer_for(app, real_redis, sessions)
    await consumer.ensure_group()
    await publish_upload(app, client, real_redis, user_factory)
    await consumer.process_new()
    assert await counts(app) == (0, 0)
    assert await pending(real_redis) == 1
    assert await real_redis.xlen(OUTCOME) == 0


async def test_failed_event_is_redelivered_by_xautoclaim_and_attached_once(
    app, client, real_redis, user_factory
) -> None:
    sessions = FailingCommitSessions(app.state.session_factory, failures=1)
    consumer = consumer_for(app, real_redis, sessions)
    await consumer.ensure_group()
    await publish_upload(app, client, real_redis, user_factory)
    await consumer.process_new()
    await consumer.process_stale()
    assert await counts(app) == (1, 1)
    assert await pending(real_redis) == 0
    await consumer.process_stale()
    assert await counts(app) == (1, 1)


async def test_duplicate_events_create_exactly_one_message(
    app, client, real_redis, user_factory
) -> None:
    consumer = consumer_for(app, real_redis)
    await consumer.ensure_group()
    event = await publish_upload(app, client, real_redis, user_factory)
    await real_redis.xadd(COMPLETED, event)
    await consumer.process_new()
    assert await counts(app) == (1, 1)
    outcomes = await real_redis.xrange(OUTCOME)
    assert [fields["type"] for _, fields in outcomes] == ["upload.attached", "upload.attached"]
    assert len({fields["message_id"] for _, fields in outcomes}) == 1


async def test_event_is_dead_lettered_after_max_deliveries(
    app, client, real_redis, user_factory
) -> None:
    sessions = FailingCommitSessions(app.state.session_factory, failures=100)
    consumer = consumer_for(app, real_redis, sessions, max_deliveries=2)
    await consumer.ensure_group()
    event = await publish_upload(app, client, real_redis, user_factory)
    await consumer.process_new()
    await consumer.process_stale()
    await consumer.process_stale()
    assert await pending(real_redis) == 0
    [(_, dead)] = await real_redis.xrange(dead_letter_stream(COMPLETED))
    assert dead["upload_id"] == event["upload_id"]
    assert await counts(app) == (0, 0)


async def test_attached_upload_is_never_dead_lettered(
    app, client, real_redis, user_factory
) -> None:
    consumer = consumer_for(app, real_redis, max_deliveries=1)
    await consumer.ensure_group()
    await publish_upload(app, client, real_redis, user_factory)
    await consumer.process_new()
    event = (await real_redis.xrange(COMPLETED))[0][1]
    await real_redis.xadd(COMPLETED, event)
    broken = consumer_for(
        app, real_redis, max_deliveries=1,
        publisher=UnreachableOutcomeStream(real_redis, OUTCOME, 1000),
    )
    await broken.process_new()
    for _ in range(3):
        await broken.process_stale()
    assert await pending(real_redis) == 1
    assert await real_redis.xlen(dead_letter_stream(COMPLETED)) == 0
    assert await counts(app) == (1, 1)
