from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from datetime import datetime

from file_service.domain.events import UploadCompleted
from file_service.domain.ticket import UploadTicket
from file_service.domain.upload_session import UploadSession, UploadStatus


class UploadSessionRepository(ABC):
    @abstractmethod
    async def get(self, upload_id: str) -> UploadSession | None: ...

    @abstractmethod
    async def add(self, session: UploadSession) -> bool:
        """Insert; return False when a session with this upload_id already exists."""

    @abstractmethod
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
        """Compare-and-set the status; return True only if this call changed it."""

    @abstractmethod
    async def touch(self, upload_id: str, now: datetime) -> None: ...

    @abstractmethod
    async def mark_published(self, upload_id: str, event_id: str) -> None: ...

    @abstractmethod
    async def list_unpublished_completed(
        self, older_than: datetime, limit: int
    ) -> list[UploadSession]: ...

    @abstractmethod
    async def list_by_status(
        self, statuses: Iterable[UploadStatus], older_than: datetime, limit: int
    ) -> list[UploadSession]: ...


class Transaction(ABC):
    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...


@dataclass(frozen=True)
class AssemblyResult:
    size_bytes: int
    sha256: str
    head: bytes


class ChunkStore(ABC):
    @abstractmethod
    async def write(
        self, upload_id: str, index: int, body: AsyncIterator[bytes], expected_length: int
    ) -> None: ...

    @abstractmethod
    def received(self, upload_id: str) -> set[int]: ...

    @abstractmethod
    def chunk_paths(self, upload_id: str, total_chunks: int) -> list[str]: ...

    @abstractmethod
    def delete(self, upload_id: str) -> None: ...

    @abstractmethod
    def list_upload_dirs(self, older_than: datetime) -> list[str]: ...


class MediaStore(ABC):
    @abstractmethod
    def allocate_path(self, mime_type: str) -> str: ...

    @abstractmethod
    async def assemble(self, upload_id: str, chunk_paths: list[str]) -> AssemblyResult: ...

    @abstractmethod
    def publish(self, upload_id: str, file_path: str) -> None: ...

    @abstractmethod
    def discard(self, upload_id: str, file_path: str | None) -> None: ...


class TicketVerifier(ABC):
    @abstractmethod
    def verify(self, token: str) -> UploadTicket: ...


class CompletionPublisher(ABC):
    @abstractmethod
    async def publish_completed(self, event: UploadCompleted) -> str:
        """Append to the completion stream; return the stream entry id."""


class StreamSettlement(ABC):
    @abstractmethod
    async def is_settled(self, upload_id: str, completed_event_id: str) -> bool:
        """True only when the backend has acked the completion and every outcome was applied."""


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime: ...
