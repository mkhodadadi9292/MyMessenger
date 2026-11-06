import asyncio
import logging
import os
import socket
import uuid
from collections.abc import Awaitable, Callable

from redis.asyncio import Redis
from redis.exceptions import RedisError, ResponseError

from file_service.domain.events import SCHEMA_VERSION, UPLOAD_COMPLETED, UploadCompleted
from file_service.domain.ports import CompletionPublisher, StreamSettlement

logger = logging.getLogger("file_service.streams")

EventHandler = Callable[[dict[str, str]], Awaitable[None]]
KeepPendingCheck = Callable[[dict[str, str]], Awaitable[bool]]


class PermanentEventError(Exception):
    pass


def dead_letter_stream(stream: str) -> str:
    return f"{stream}.dead"


def default_consumer_name() -> str:
    return f"{socket.gethostname()}-{os.getpid()}"


def parse_stream_id(entry_id: str) -> tuple[int, int]:
    millis, _, sequence = entry_id.partition("-")
    return int(millis), int(sequence or 0)


class RedisCompletionPublisher(CompletionPublisher):
    def __init__(self, redis: Redis, stream: str, maxlen: int) -> None:
        self._redis = redis
        self._stream = stream
        self._maxlen = maxlen

    async def publish_completed(self, event: UploadCompleted) -> str:
        fields = {
            "schema_version": SCHEMA_VERSION,
            "event_id": uuid.uuid4().hex,
            "type": UPLOAD_COMPLETED,
            "upload_id": event.upload_id,
            "ticket": event.ticket,
            "file_path": event.file_path,
            "size_bytes": str(event.size_bytes),
            "sha256": event.sha256,
            "mime_type": event.mime_type,
            "completed_at": event.completed_at.isoformat() + "Z",
        }
        return await self._redis.xadd(
            self._stream, fields, maxlen=self._maxlen, approximate=True
        )


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
            except (RedisError, OSError):
                logger.warning("redis unavailable for %s; retrying", self.stream, exc_info=True)
                await _sleep_or_stop(stop, 2)
            except Exception:
                logger.exception("stream loop error on %s", self.stream)
                await _sleep_or_stop(stop, 2)


async def _sleep_or_stop(stop: asyncio.Event, seconds: float) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconds)
    except TimeoutError:
        pass


class RedisStreamSettlement(StreamSettlement):
    def __init__(
        self,
        redis: Redis,
        completed_stream: str,
        backend_group: str,
        outcome_stream: str,
        outcome_group: str,
    ) -> None:
        self._redis = redis
        self._completed_stream = completed_stream
        self._backend_group = backend_group
        self._outcome_stream = outcome_stream
        self._outcome_group = outcome_group

    async def _group(self, stream: str, name: str) -> dict | None:
        try:
            groups = await self._redis.xinfo_groups(stream)
        except ResponseError:
            return None
        for group in groups:
            if group.get("name") == name:
                return group
        return None

    async def _fully_delivered(self, stream: str, group: dict) -> bool:
        lag = group.get("lag")
        if lag is not None:
            return int(lag) == 0
        info = await self._redis.xinfo_stream(stream)
        last_generated = str(info.get("last-generated-id", "0-0"))
        last_delivered = str(group.get("last-delivered-id", "0-0"))
        return parse_stream_id(last_generated) <= parse_stream_id(last_delivered)

    async def _in_dead_letters(self, stream: str, upload_id: str) -> bool:
        entries = await self._redis.xrange(dead_letter_stream(stream))
        return any(fields.get("upload_id") == upload_id for _, fields in entries)

    async def is_settled(self, upload_id: str, completed_event_id: str) -> bool:
        backend = await self._group(self._completed_stream, self._backend_group)
        if backend is None:
            return False
        last_delivered = str(backend.get("last-delivered-id", "0-0"))
        if parse_stream_id(completed_event_id) > parse_stream_id(last_delivered):
            return False
        still_pending = await self._redis.xpending_range(
            self._completed_stream,
            self._backend_group,
            min=completed_event_id,
            max=completed_event_id,
            count=1,
        )
        if still_pending:
            return False
        outcome = await self._group(self._outcome_stream, self._outcome_group)
        if outcome is None:
            return False
        if not await self._fully_delivered(self._outcome_stream, outcome):
            return False
        if int(outcome.get("pending", 0)) != 0:
            return False
        if await self._in_dead_letters(self._completed_stream, upload_id):
            return False
        if await self._in_dead_letters(self._outcome_stream, upload_id):
            return False
        return True
