from abc import ABC, abstractmethod


class IDownloadAccessStore(ABC):
    @abstractmethod
    async def is_allowed(self, public_id: str, lookup_key: str) -> bool: ...

    @abstractmethod
    async def allow(self, public_id: str, lookup_key: str) -> None: ...