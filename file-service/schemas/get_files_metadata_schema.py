from pydantic import BaseModel
from typing import List


class GetFilesMetadataRequest(BaseModel):
    lookup_keys: List[str]


class FileMetadataResponse(BaseModel):
    id: str
    lookup_key: str
    name: str
    size_bytes: int
    has_thumbnail: bool
    is_private: bool
    file_kind: str
