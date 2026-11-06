from datetime import datetime
from core.entities.file_kind import FileKind
from core.entities.file_size_class import FileSizeClass

class File:
    def __init__(
        self,
        file_id: str,
        lookup_key: str,
        name: str,
        file_hash: str,
        size_bytes: int,
        size_class: FileSizeClass,
        has_thumbnail: bool,
        is_private: bool,
        committed: bool,
        last_seen_at: datetime,
        mime_type: FileKind,
    ):
        self.file_id = file_id
        self.lookup_key = lookup_key
        self.name = name
        self.file_hash = file_hash
        self.size_bytes = size_bytes
        self.size_class = size_class
        self.has_thumbnail = has_thumbnail
        self.is_private = is_private
        self.committed = committed
        self.last_seen_at = last_seen_at
        self.mime_type = mime_type
