from abc import abstractmethod

from app.domain.entities import Notification
from app.domain.repositories.base import AbstractRepository


class NotificationRepository(AbstractRepository[Notification, int]):
    @abstractmethod
    async def list_for_user(
        self, user_id: int, before_id: int | None, limit: int
    ) -> list[Notification]:
        """Newest-first cursor page of the user's notifications."""

    @abstractmethod
    async def unread_count(self, user_id: int) -> int:
        ...

    @abstractmethod
    async def mark_read(self, user_id: int, chat_id: int | None) -> int:
        """Bulk mark-read (all, or one chat); returns rows affected."""
