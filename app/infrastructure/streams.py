import asyncio
import logging
import os
import socket
import uuid
from collections.abc import Awaitable, Callable

from redis.asyncio import Redis
from redis.exceptions import RedisError, ResponseError

from app.application.ports import UploadOutcomePublisher
from app.domain.time import utcnow

logger = logging.getLogger("app.streams")

SCHEMA_VERSION = "1"
UPLOAD_ATTACHED = "upload.attached"
UPLOAD_REJECTED = "upload.rejected"

EventHandler = Callable[[dict[str, str]], Awaitable[None]]
KeepPendingCheck = Callable[[dict[str, str]], Awaitable[bool]]


class PermanentEventError(Exception):
    pass


def dead_letter_stream(stream: str) -> str:
    return f"{stream}.dead"


def default_consumer_name() -> str:
    return f"{socket.gethostname()}-{os.getpid()}"


class RedisUploadOutcomePublisher(UploadOutcomePublisher):
    def __init__(self, redis: Redis, stream: str, maxlen: int) -> None:
        self._redis = redis
        self._stream = stream
        self._maxlen = maxlen

    async def _publish(self, fields: dict[str, str]) -> None:
        await self._redis.xadd(
            self._stream,
            {
                "schema_version": SCHEMA_VERSION,
                "event_id": uuid.uuid4().hex,
                "decided_at": utcnow().isoformat() + "Z",
                **fields,
            },
            maxlen=self._maxlen,
            approximate=True,
        )

    async def publish_attached(self, upload_id: str, message_id: int, artifact_id: int) -> None:
        await self._publish(
            {
                "type": UPLOAD_ATTACHED,
                "upload_id": upload_id,
                "message_id": str(message_id),
                "artifact_id": str(artifact_id),
            }
        )

    async def publish_rejected(self, upload_id: str, reason: str) -> None:
        await self._publish({"type": UPLOAD_REJECTED, "upload_id": upload_id, "reason": reason})


class StreamConsumer:
    def __init__(
        self,
        redis: Redis,
        stream: str,
        group: str,
        handler: EventHandler,
        *,
        consumer: str | None = None,
        max_deliveries: int = 5,
        claim_min_idle_ms: int = 60_000,
        claim_interval_seconds: float = 30,
        block_ms: int = 5000,
        batch_size: int = 10,
        keep_pending: KeepPendingCheck | None = None,
    ) -> None:
        self._redis = redis
        self.stream = stream
        self.group = group
        self._handler = handler
        self.consumer = consumer or default_consumer_name()
        self._max_deliveries = max_deliveries
        self._claim_min_idle_ms = claim_min_idle_ms
        self._claim_interval_seconds = claim_interval_seconds
        self._block_ms = block_ms
        self._batch_size = batch_size
        self._keep_pending = keep_pending

    async def ensure_group(self) -> None:
        try:
            await self._redis.xgroup_create(self.stream, self.group, id="0", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def process_new(self) -> int:
        response = await self._redis.xreadgroup(
            self.group,
            self.consumer,
            {self.stream: ">"},
            count=self._batch_size,
            block=self._block_ms,
        )
        handled = 0
        for _, entries in response or []:
            for entry_id, fields in entries:
                await self._handle(entry_id, fields)
                handled += 1
        return handled

    async def process_stale(self) -> int:
        result = await self._redis.xautoclaim(
            self.stream,
            self.group,
            self.consumer,
            min_idle_time=self._claim_min_idle_ms,
            start_id="0-0",
            count=self._batch_size,
        )
        claimed = result[1]
        handled = 0
        for entry_id, fields in claimed:
            if fields is None:
                await self._redis.xack(self.stream, self.group, entry_id)
                continue
            deliveries = await self._delivery_count(entry_id)
            if deliveries > self._max_deliveries and not await self._must_keep(fields):
                await self._dead_letter(entry_id, fields, deliveries, "max deliveries exceeded")
            else:
                await self._handle(entry_id, fields)
            handled += 1
        return handled

    async def _must_keep(self, fields: dict[str, str]) -> bool:
        if self._keep_pending is None:
            return False
        try:
            return await self._keep_pending(fields)
        except Exception:
            logger.exception("keep-pending check failed on %s; keeping the entry", self.stream)
            return True

    async def _delivery_count(self, entry_id: str) -> int:
        pending = await self._redis.xpending_range(
            self.stream, self.group, min=entry_id, max=entry_id, count=1
        )
        return int(pending[0]["times_delivered"]) if pending else 0

    async def _handle(self, entry_id: str, fields: dict[str, str]) -> None:
        try:
            await self._handler(fields)
        except PermanentEventError as exc:
            deliveries = await self._delivery_count(entry_id)
            await self._dead_letter(entry_id, fields, deliveries, str(exc))
            return
        except Exception:
            logger.exception("handling %s %s failed; it stays pending", self.stream, entry_id)
            return
        await self._redis.xack(self.stream, self.group, entry_id)

    async def _dead_letter(
        self, entry_id: str, fields: dict[str, str], deliveries: int, error: str
    ) -> None:
        await self._redis.xadd(
            dead_letter_stream(self.stream),
            {**fields, "source_id": entry_id, "deliveries": str(deliveries), "error": error[:500]},
        )
        await self._redis.xack(self.stream, self.group, entry_id)
        logger.error("moved %s %s to dead letters: %s", self.stream, entry_id, error)

    async def run(self, stop: asyncio.Event) -> None:
        loop = asyncio.get_running_loop()
        next_claim = 0.0
        while not stop.is_set():
            try:
                await self.ensure_group()
                if loop.time() >= next_claim:
                    await self.process_stale()
                    next_claim = loop.time() + self._claim_interval_seconds
                await self.process_new()
            except asyncio.CancelledError:
                raise
            except (RedisError, OSError) as exc:
                logger.warning("redis unavailable for %s (%s); retrying", self.stream, exc)
                await _sleep_or_stop(stop, 2)
            except Exception:
                logger.exception("stream loop error on %s", self.stream)
                await _sleep_or_stop(stop, 2)


async def _sleep_or_stop(stop: asyncio.Event, seconds: float) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconds)
    except TimeoutError:
        pass
