from core.interfaces.file_storage import IFileStorage
from core.interfaces.thumbnail_service import IThumbnailService
from core.interfaces.file_repository import IFileRepository

class DeleteFileBySessionCleanupUC:
    def __init__(
        self,
        storage: IFileStorage,
        file_repo: IFileRepository,
        thumbnail_service: IThumbnailService,
    ):
        self.storage = storage
        self.file_repo = file_repo
        self.thumbnail_service = thumbnail_service

    async def execute(self, session_id: str):
        await self.storage.delete_file(session_id)
        await self.thumbnail_service.delete_thumbnail(session_id)
        await self.file_repo.delete_file_record(session_id)
        return {"status": "deleted"}
