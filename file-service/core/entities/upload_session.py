from dataclasses import dataclass
from typing import Optional


@dataclass
class UploadSession:
    session_id: str
    public_id: str
    last_chunk_number: int
    hash_in_last: bool = False
    file_type: Optional[str] = None
    total_chunks: Optional[int] = None
