from abc import abstractmethod

from app.domain.entities import Block, Contact
from app.domain.repositories.base import AbstractRepository


class ContactRepository(AbstractRepository[Contact, int]):
    @abstractmethod
    async def get_pair(self, owner_id: int, contact_id: int) -> Contact | None:
        ...

    @abstractmethod
    async def list_by_owner(self, owner_id: int) -> list[Contact]:
        ...

    @abstractmethod
    async def remove(self, owner_id: int, contact_id: int) -> None:
        ...


class BlockRepository(AbstractRepository[Block, int]):
    @abstractmethod
    async def get_pair(self, blocker_id: int, blocked_id: int) -> Block | None:
        ...

    @abstractmethod
    async def list_by_blocker(self, blocker_id: int) -> list[Block]:
        ...

    @abstractmethod
    async def blocks_either(self, user_a: int, user_b: int) -> bool:
        ...

    @abstractmethod
    async def blockers_of(self, blocked_id: int) -> set[int]:
        ...

    @abstractmethod
    async def remove(self, blocker_id: int, blocked_id: int) -> None:
        ...
