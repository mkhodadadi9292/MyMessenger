from core.interfaces.cleaner_repository import ICleanerRepository
from core.interfaces.file_store import IFileStore
from core.interfaces.cleanup_api import ICleanupAPI

class CleanupUploadingFilesUC:
    def __init__(self, repo: ICleanerRepository, store: IFileStore, api: ICleanupAPI):
        self.repo = repo
        self.store = store
        self.api = api

    async def execute(self):
        sessions = await self.repo.get_all_uploading_sessions()
        for session in sessions:
            if await self.store.exists(session.session_id):
                continue
            await self.api.cleanup(session.session_id)
