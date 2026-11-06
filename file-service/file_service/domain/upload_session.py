from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from file_service.domain.chunk_plan import ChunkPlan


class UploadStatus(StrEnum):
    ACTIVE = "active"
    ASSEMBLING = "assembling"
    COMPLETED = "completed"
    ATTACHED = "attached"
    REJECTED = "rejected"
    FAILED = "failed"
    ABORTED = "aborted"
    EXPIRED = "expired"
    PURGED = "purged"


PURGEABLE_TERMINAL_STATUSES: frozenset[UploadStatus] = frozenset(
    {UploadStatus.REJECTED, UploadStatus.FAILED, UploadStatus.ABORTED, UploadStatus.EXPIRED}
)


@dataclass
class UploadSession:
    upload_id: str
    user_id: int
    mime_type: str
    size_bytes: int
    sha256: str
    chunk_size: int
    total_chunks: int
    status: UploadStatus
    ticket: str
    created_at: datetime
    last_activity_at: datetime
    file_path: str | None = None
    completed_event_id: str | None = None
    failure_reason: str | None = None
    completed_at: datetime | None = None
    decided_at: datetime | None = None

    @property
    def plan(self) -> ChunkPlan:
        return ChunkPlan(self.size_bytes, self.chunk_size)

    @property
    def is_finished(self) -> bool:
        return self.status in (UploadStatus.COMPLETED, UploadStatus.ATTACHED)
