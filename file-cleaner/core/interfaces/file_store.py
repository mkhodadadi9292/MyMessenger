from abc import ABC, abstractmethod

class IFileStore(ABC):
    @abstractmethod
    async def exists(self, session_id: str) -> bool:
        pass
