from abc import abstractmethod
from collections.abc import Sequence

from app.domain.repositories.base import AbstractRepository
from app.domain.entities import Artifact, Message, Reaction

class MessageRepository(AbstractRepository[Message, int]):
    @abstractmethod
    async def list_page(self, chat_id: int, before_id: int | None, limit: int) -> list[Message]:
        """Newest-first page of messages; if before_id is set, only older messages."""

    @abstractmethod
    async def last_for_chats(self, chat_ids: Sequence[int]) -> dict[int, Message]:
        ...

    @abstractmethod
    async def list_by_ids(self, message_ids: Sequence[int]) -> list[Message]:
        ...

    @abstractmethod
    async def update(self, entity: Message) -> Message:
        ...


class ArtifactRepository(AbstractRepository[Artifact, int]):
    @abstractmethod
    async def list_by_message_ids(self, message_ids: Sequence[int]) -> list[Artifact]:
        ...

class ReactionRepository(AbstractRepository[Reaction, int]):
    @abstractmethod
    async def get_pair(self, message_id: int, user_id: int) -> Reaction | None:
        ...

    @abstractmethod
    async def list_by_message_ids(self, message_ids: Sequence[int]) -> list[Reaction]:
        ...

    @abstractmethod
    async def update(self, entity: Reaction) -> Reaction:
        ...