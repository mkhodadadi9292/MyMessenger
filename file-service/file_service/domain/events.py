from dataclasses import dataclass
from datetime import datetime

UPLOAD_COMPLETED = "upload.completed"
UPLOAD_ATTACHED = "upload.attached"
UPLOAD_REJECTED = "upload.rejected"
SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class UploadCompleted:
    upload_id: str
    ticket: str
    file_path: str
    size_bytes: int
    sha256: str
    mime_type: str
    completed_at: datetime


@dataclass(frozen=True)
class UploadOutcome:
    type: str
    upload_id: str
