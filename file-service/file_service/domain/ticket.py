import re
from dataclasses import dataclass

from file_service.domain.exceptions import UnauthorizedError

_UPLOAD_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class UploadTicket:
    upload_id: str
    user_id: int
    mime_type: str
    size_bytes: int
    sha256: str
    raw: str

    def __post_init__(self) -> None:
        if not _UPLOAD_ID_RE.fullmatch(self.upload_id):
            raise UnauthorizedError("ticket has an invalid upload_id")
        if not _SHA256_RE.fullmatch(self.sha256):
            raise UnauthorizedError("ticket has an invalid sha256")
        if self.size_bytes <= 0:
            raise UnauthorizedError("ticket has an invalid size")

    def require_upload(self, upload_id: str) -> None:
        if upload_id != self.upload_id:
            raise UnauthorizedError("ticket does not belong to this upload")
