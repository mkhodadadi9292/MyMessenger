from abc import ABC, abstractmethod
from typing import Generic, TypeVar

TEntity = TypeVar("TEntity")
TId = TypeVar("TId")


class AbstractRepository(ABC, Generic[TEntity, TId]):
    """Port implemented by infrastructure (SQLAlchemy) and test fakes."""

    @abstractmethod
    async def get(self, entity_id: TId) -> TEntity | None:
        ...

    @abstractmethod
    async def add(self, entity: TEntity) -> TEntity:
        ...

    @abstractmethod
    async def delete(self, entity: TEntity) -> None:
        ...
