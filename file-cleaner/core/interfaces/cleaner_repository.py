from abc import ABC, abstractmethod
from typing import List
from core.entities.uploading_file import UploadingFile
from core.entities.file import File

class ICleanerRepository(ABC):
    @abstractmethod
    async def get_all_uploading_sessions(self) -> List[UploadingFile]:
        pass

    @abstractmethod
    async def get_uncommitted_files(self, threshold_minutes: int) -> List[File]:
        pass

    @abstractmethod
    async def get_expired_files(self) -> List[File]:
        pass