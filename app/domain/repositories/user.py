from abc import abstractmethod
from collections.abc import Sequence

from app.domain.entities import User
from app.domain.repositories.base import AbstractRepository


class UserRepository(AbstractRepository[User, int]):
    @abstractmethod
    async def get_by_username(self, username: str) -> User | None:
        ...

    @abstractmethod
    async def get_by_identifier(self, identifier: str) -> User | None:
        ...

    @abstractmethod
    async def list_by_ids(self, user_ids: Sequence[int]) -> list[User]:
        ...

    @abstractmethod
    async def search(self, query: str) -> list[User]:
        """Username prefix search, or exact phone match when query starts with '+'."""

    @abstractmethod
    async def update(self, entity: User) -> User:
        ...
