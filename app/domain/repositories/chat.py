from abc import abstractmethod
from collections.abc import Sequence

from app.domain.entities import Chat, ChatMember, Invite
from app.domain.repositories.base import AbstractRepository


class ChatRepository(AbstractRepository[Chat, int]):
    @abstractmethod
    async def find_private_chat(self, user_a: int, user_b: int) -> Chat | None:
        ...

    @abstractmethod
    async def list_for_user(self, user_id: int) -> list[Chat]:
        ...

    @abstractmethod
    async def list_by_ids(self, chat_ids: Sequence[int]) -> list[Chat]:
        ...

    @abstractmethod
    async def update(self, entity: Chat) -> Chat:
        ...

    @abstractmethod
    async def delete_with_contents(self, chat_id: int) -> None:
        ...


class ChatMemberRepository(AbstractRepository[ChatMember, int]):
    @abstractmethod
    async def get_pair(self, chat_id: int, user_id: int) -> ChatMember | None:
        ...

    @abstractmethod
    async def list_by_chat(self, chat_id: int) -> list[ChatMember]:
        ...

    @abstractmethod
    async def remove(self, chat_id: int, user_id: int) -> None:
        ...

    @abstractmethod
    async def update(self, entity: ChatMember) -> ChatMember:
        ...


class InviteRepository(AbstractRepository[Invite, int]):
    @abstractmethod
    async def get_by_token(self, token: str) -> Invite | None:
        ...

    @abstractmethod
    async def get_pending(self, chat_id: int, invitee_id: int) -> Invite | None:
        ...

    @abstractmethod
    async def list_pending_for_invitee(self, invitee_id: int) -> list[Invite]:
        ...

    @abstractmethod
    async def update(self, entity: Invite) -> Invite:
        ...
