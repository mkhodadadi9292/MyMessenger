import hashlib
import uuid
from collections.abc import AsyncIterator, Iterable
from dataclasses import replace
from datetime import datetime, timedelta

from file_service.domain.events import UploadCompleted
from file_service.domain.exceptions import PayloadTooLargeError, ValidationError
from file_service.domain.media_type import EXTENSION_BY_MIME, SNIFF_BYTES
from file_service.domain.ports import (
    AssemblyResult,
    ChunkStore,
    Clock,
    CompletionPublisher,
    MediaStore,
    StreamSettlement,
    Transaction,
    UploadSessionRepository,
)
from file_service.domain.upload_session import UploadSession, UploadStatus


class FixedClock(Clock):
    def __init__(self, now: datetime | None = None) -> None:
        self.current = now or datetime(2026, 1, 1, 12, 0, 0)

    def now(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


class InMemorySessionRepository(UploadSessionRepository):
    def __init__(self) -> None:
        self.rows: dict[str, UploadSession] = {}

    async def get(self, upload_id: str) -> UploadSession | None:
        row = self.rows.get(upload_id)
        return replace(row) if row else None

    async def add(self, session: UploadSession) -> bool:
        if session.upload_id in self.rows:
            return False
        self.rows[session.upload_id] = replace(session)
        return True

    async def transition(
        self,
        upload_id: str,
        from_statuses: Iterable[UploadStatus],
        to_status: UploadStatus,
        now: datetime,
        *,
        older_than: datetime | None = None,
        file_path: str | None = None,
        failure_reason: str | None = None,
        completed: bool = False,
        decided: bool = False,
    ) -> bool:
        row = self.rows.get(upload_id)
        if row is None or row.status not in set(from_statuses):
            return False
        if older_than is not None and not row.last_activity_at < older_than:
            return False
        row.status = to_status
        row.last_activity_at = now
        if file_path is not None:
            row.file_path = file_path
        if failure_reason is not None:
            row.failure_reason = failure_reason
        if completed:
            row.completed_at = now
        if decided:
            row.decided_at = now
        return True

    async def touch(self, upload_id: str, now: datetime) -> None:
        self.rows[upload_id].last_activity_at = now

    async def mark_published(self, upload_id: str, event_id: str) -> None:
        self.rows[upload_id].completed_event_id = event_id

    async def list_unpublished_completed(self, older_than, limit):
        return [
            replace(r)
            for r in self.rows.values()
            if r.status is UploadStatus.COMPLETED
            and r.completed_event_id is None
            and r.completed_at is not None
            and r.completed_at < older_than
        ][:limit]

    async def list_by_status(self, statuses, older_than, limit):
        wanted = set(statuses)
        return [
            replace(r)
            for r in self.rows.values()
            if r.status in wanted and r.last_activity_at < older_than
        ][:limit]


class CountingTransaction(Transaction):
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class InMemoryChunkStore(ChunkStore):
    def __init__(self) -> None:
        self.chunks: dict[str, dict[int, bytes]] = {}
        self.dir_ages: dict[str, datetime] = {}

    async def write(
        self, upload_id: str, index: int, body: AsyncIterator[bytes], expected_length: int
    ) -> None:
        data = b""
        async for piece in body:
            data += piece
            if len(data) > expected_length:
                raise PayloadTooLargeError("too large")
        if len(data) != expected_length:
            raise ValidationError("too short")
        self.chunks.setdefault(upload_id, {})[index] = data

    def received(self, upload_id: str) -> set[int]:
        return set(self.chunks.get(upload_id, {}))

    def chunk_paths(self, upload_id: str, total_chunks: int) -> list[str]:
        return [f"{upload_id}/{index}" for index in range(total_chunks)]

    def delete(self, upload_id: str) -> None:
        self.chunks.pop(upload_id, None)
        self.dir_ages.pop(upload_id, None)

    def list_upload_dirs(self, older_than: datetime) -> list[str]:
        return sorted(u for u, age in self.dir_ages.items() if age < older_than)


class InMemoryMediaStore(MediaStore):
    def __init__(self, chunks: InMemoryChunkStore) -> None:
        self._chunks = chunks
        self.partials: dict[str, bytes] = {}
        self.files: dict[str, bytes] = {}

    def allocate_path(self, mime_type: str) -> str:
        return f"artifacts/{uuid.uuid4().hex}{EXTENSION_BY_MIME[mime_type]}"

    async def assemble(self, upload_id: str, chunk_paths: list[str]) -> AssemblyResult:
        stored = self._chunks.chunks[upload_id]
        data = b"".join(stored[int(p.rsplit("/", 1)[1])] for p in chunk_paths)
        self.partials[upload_id] = data
        return AssemblyResult(len(data), hashlib.sha256(data).hexdigest(), data[:SNIFF_BYTES])

    def publish(self, upload_id: str, file_path: str) -> None:
        self.files[file_path] = self.partials.pop(upload_id)

    def discard(self, upload_id: str, file_path: str | None) -> None:
        self.partials.pop(upload_id, None)
        if file_path is not None:
            self.files.pop(file_path, None)


class RecordingPublisher(CompletionPublisher):
    def __init__(self, fail: bool = False) -> None:
        self.events: list[UploadCompleted] = []
        self.fail = fail

    async def publish_completed(self, event: UploadCompleted) -> str:
        if self.fail:
            raise ConnectionError("redis down")
        self.events.append(event)
        return f"{len(self.events)}-0"


class StaticSettlement(StreamSettlement):
    def __init__(self, settled: bool) -> None:
        self.settled = settled

    async def is_settled(self, upload_id: str, completed_event_id: str) -> bool:
        return self.settled


async def body_of(data: bytes, piece: int = 4096) -> AsyncIterator[bytes]:
    for start in range(0, len(data), piece):
        yield data[start : start + piece]
