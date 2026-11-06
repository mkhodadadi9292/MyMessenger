from dataclasses import dataclass
from typing import Optional
from core.entities.file_kind import FileKind
from core.entities.file_size_class import FileSizeClass


@dataclass
class File:
    id: str
    lookup_key: str
    name: str
    hash: str
    size_bytes: int
    size_class: FileSizeClass
    has_thumbnail: bool
    is_private: bool
    committed: bool
    usage_count: int
    protected_count: int
    last_seen_at: Optional[str]
    mime_type: FileKind
