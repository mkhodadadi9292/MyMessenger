from dataclasses import dataclass
from datetime import datetime

@dataclass
class UploadingFile:
    session_id: str
    created_at: datetime
