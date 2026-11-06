import re
from dataclasses import dataclass
from datetime import datetime

from app.domain.exceptions import ValidationError
from app.domain.value_objects import ArtifactKind

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_UPLOAD_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_STORED_ARTIFACT_PATH_RE = re.compile(r"^artifacts/[0-9a-f]{32}\.[a-z0-9]{2,5}$")
MAX_FILE_NAME_LENGTH = 255


def is_upload_id(value: str) -> bool:
    return bool(_UPLOAD_ID_RE.fullmatch(value))


def is_stored_artifact_path(value: str) -> bool:
    return bool(_STORED_ARTIFACT_PATH_RE.fullmatch(value))


@dataclass(frozen=True)
class UploadRequest:
    file_name: str
    size_bytes: int
    mime_type: str
    kind: ArtifactKind
    sha256: str
    reply_to_id: int | None = None

    def validate(self, max_size_bytes: int) -> None:
        if not self.file_name.strip() or len(self.file_name) > MAX_FILE_NAME_LENGTH:
            raise ValidationError(f"file_name must be 1-{MAX_FILE_NAME_LENGTH} characters")
        if self.size_bytes <= 0:
            raise ValidationError("size_bytes must be positive")
        if self.size_bytes > max_size_bytes:
            raise ValidationError("artifact is too large")
        if not self.kind.accepts_mime(self.mime_type):
            raise ValidationError(f"mime type {self.mime_type} is not valid for {self.kind.value}")
        if not _SHA256_RE.fullmatch(self.sha256):
            raise ValidationError("sha256 must be 64 lowercase hex characters")


@dataclass(frozen=True)
class UploadTicketClaims:
    upload_id: str
    user_id: int
    chat_id: int
    kind: ArtifactKind
    mime_type: str
    size_bytes: int
    sha256: str
    file_name: str
    reply_to_id: int | None
    issued_at: datetime


@dataclass(frozen=True)
class IssuedTicket:
    upload_id: str
    token: str
    expires_at: datetime


@dataclass(frozen=True)
class CompletedUpload:
    upload_id: str
    ticket: str
    file_path: str
    size_bytes: int
    sha256: str
    mime_type: str


class RejectionReason:
    CHAT_NOT_FOUND = "chat_not_found"
    NOT_MEMBER = "not_member"
    BLOCKED = "blocked"
    INVALID_TICKET = "invalid_ticket"
    INVALID_EVENT = "invalid_event"
    TOO_OLD = "too_old"
