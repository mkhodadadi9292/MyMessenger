from abc import ABC, abstractmethod

class IBlockStore(ABC):
    @abstractmethod
    async def is_blocked(self, lookup_key: str, req_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def block(self, lookup_key: str, req_id: str) -> None:
        raise NotImplementedError
