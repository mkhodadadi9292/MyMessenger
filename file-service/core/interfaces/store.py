from abc import ABC, abstractmethod
from typing import Optional
from core.entities.upload_session import UploadSession


class IStore(ABC):

    @abstractmethod
    async def init_session(self, session_id: str, public_id: str):
        raise NotImplementedError

    @abstractmethod
    async def update_session(
        self,
        session_id: str,
        public_id: str,
        last_chunk_number: int,
        hash_in_last: bool,
        file_type: Optional[str],
        total_chunks: Optional[int],
    ):
        raise NotImplementedError

    @abstractmethod
    async def load(self, session_id: str) -> Optional[UploadSession]:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, session_id: str):
        raise NotImplementedError
