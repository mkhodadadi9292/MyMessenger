from typing import List
from core.entities.file_metadata import FileMetadata
from core.interfaces.file_repository import IFileRepository
from core.interfaces.metadata_store import IMetadataStore

class GetFilesMetadataBatchUC:
    def __init__(self, file_repo: IFileRepository, metadata_store: IMetadataStore):
        self.file_repo = file_repo
        self.metadata_store = metadata_store

    async def execute(self, lookup_keys: List[str]) -> List[FileMetadata]:
        cached_results = await self.metadata_store.get_batch(lookup_keys)

        results: List[FileMetadata] = []
        missing_keys: List[str] = []
        for key, cached in zip(lookup_keys, cached_results):
            if cached:
                results.append(cached)
            else:
                missing_keys.append(key)

        if missing_keys:
            db_results = await self.file_repo.get_metadata_batch(missing_keys)

            for file in db_results:
                await self.metadata_store.set(file)
                results.append(file)

        return results
