from abc import ABC, abstractmethod

class ICleanupAPI(ABC):
    @abstractmethod
    async def cleanup(self, session_id: str) -> None:
        pass

    @abstractmethod
    async def delete(self, session_id: str) -> None:
        pass
