from core.interfaces.file_repository import IFileRepository


class CommitFileUC:
    def __init__(self, file_repo: IFileRepository):
        self.file_repo = file_repo

    async def execute(self, lookup_key: str) -> None:
        await self.file_repo.commit_file(lookup_key)
