from abc import abstractmethod
from collections.abc import Sequence

from app.domain.entities import Artifact, Message
from app.domain.repositories.base import AbstractRepository


class MessageRepository(AbstractRepository[Message, int]):
    @abstractmethod
    async def list_page(self, chat_id: int, before_id: int | None, limit: int) -> list[Message]:
        """Newest-first page of messages; if before_id is set, only older messages."""

    @abstractmethod
    async def last_for_chats(self, chat_ids: Sequence[int]) -> dict[int, Message]:
        ...

    @abstractmethod
    async def update(self, entity: Message) -> Message:
        ...


class ArtifactRepository(AbstractRepository[Artifact, int]):
    @abstractmethod
    async def list_by_message_ids(self, message_ids: Sequence[int]) -> list[Artifact]:
        ...
