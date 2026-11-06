from core.interfaces.file_repository import IFileRepository
from core.interfaces.block_store import IBlockStore


class UpdateFileProtectUC:
    def __init__(self, file_repo: IFileRepository, block_store: IBlockStore):
        self.file_repo = file_repo
        self.block_store = block_store

    async def execute(self, lookup_key: str, req_id: str, is_protect: bool) -> dict:
        if await self.block_store.is_blocked(lookup_key, req_id):
            return {"status": "blocked"}

        await self.block_store.block(lookup_key, req_id)
        await self.file_repo.update_is_protect(lookup_key, is_protect)

        return {
            "status": "ok",
            "lookup_key": lookup_key,
            "is_protect": is_protect,
        }
