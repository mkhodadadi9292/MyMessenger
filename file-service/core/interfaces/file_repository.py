from typing import Optional, List
from core.entities.file_kind import FileKind
from core.entities.file import File
from core.entities.file_metadata import FileMetadata


class IFileRepository:
    async def find_by_hash(self, file_hash: str, is_private: bool) -> Optional[str]:
        raise NotImplementedError

    async def create_file(
        self,
        file_hash: str,
        size_bytes: int,
        size_class,
        is_private: bool,
        is_protect: bool,
        mime_type: FileKind,
        name: str,
        has_thumbnail: bool,
        session_id: str,
    ) -> str:
        raise NotImplementedError

    async def add_upload_record(self, session_id: str):
        raise NotImplementedError

    async def delete_upload_record(self, session_id: str):
        raise NotImplementedError

    async def get_by_lookup_key(self, lookup_key: str) -> Optional[File]:
        raise NotImplementedError

    async def delete_file_record(self, session_id: str):
        raise NotImplementedError

    async def decrement_usage_count(self, lookup_key: str):
        raise NotImplementedError

    async def get_metadata_batch(self, lookup_keys: List[str]) -> List[FileMetadata]:
        raise NotImplementedError

    async def commit_file(self, lookup_key: str) -> None:
        raise NotImplementedError

    async def update_is_protect(self, lookup_key: str, is_protect: bool) -> None:
        raise NotImplementedError
