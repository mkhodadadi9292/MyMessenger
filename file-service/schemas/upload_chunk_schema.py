from pydantic import BaseModel
from typing import Optional


class UploadChunkRequest(BaseModel):
    session_id: str
    chunk_number: int
    total_chunks: int
    is_private: bool
    is_protect: bool
    name: str
    resize: Optional[str] = None


class UploadChunkResponse(BaseModel):
    success: bool
    chunk_number: int
    lookup_key: Optional[str] = None
