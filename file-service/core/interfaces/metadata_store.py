from abc import ABC, abstractmethod
from typing import List, Optional
from core.entities.file_metadata import FileMetadata


class IMetadataStore(ABC):
    @abstractmethod
    async def get_batch(self, lookup_keys: List[str]) -> List[Optional[FileMetadata]]:
        raise NotImplementedError

    @abstractmethod
    async def set(self, metadata: FileMetadata):
        raise NotImplementedError
