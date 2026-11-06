from core.interfaces.file_storage import IFileStorage
from core.interfaces.thumbnail_service import IThumbnailService
from core.interfaces.file_repository import IFileRepository
from core.interfaces.block_store import IBlockStore


class DeleteFileByLookupKeyUseCase:
    def __init__(
        self,
        storage: IFileStorage,
        file_repo: IFileRepository,
        thumbnail_service: IThumbnailService,
        block_store: IBlockStore,
    ):
        self.storage = storage
        self.file_repo = file_repo
        self.thumbnail_service = thumbnail_service
        self.block_store = block_store

    async def execute(self, lookup_key: str, req_id: str):
        if await self.block_store.is_blocked(lookup_key, req_id):
            return {"status": "blocked"}

        file = await self.file_repo.get_by_lookup_key(lookup_key)
        if not file:
            return {"status": "not_found"}

        if file.usage_count == 1:
            await self.storage.delete_file(file.id)
            if file.has_thumbnail:
                await self.thumbnail_service.delete_thumbnail(file.id)
            await self.file_repo.delete_file_record(file.id)
            return {"status": "deleted"}

        await self.block_store.block(lookup_key, req_id)
        await self.file_repo.decrement_usage_count(lookup_key)
        return {"status": "decremented"}