from dataclasses import dataclass

@dataclass
class FileMetadata:
    id: str
    lookup_key: str
    name: str
    size_bytes: int
    has_thumbnail: bool
    is_private: bool
    file_kind: str
