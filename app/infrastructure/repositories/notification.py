from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Notification
from app.domain.repositories.notification import NotificationRepository
from app.domain.value_objects import NotificationType
from app.infrastructure.db.models.notification import NotificationModel


def notification_to_entity(model: NotificationModel) -> Notification:
    return Notification(
        id=model.id,
        user_id=model.user_id,
        chat_id=model.chat_id,
        type=NotificationType(model.type),
        sender_id=model.sender_id,
        message_id=model.message_id,
        invite_id=model.invite_id,
        chat_title=model.chat_title,
        preview=model.preview,
        is_read=model.is_read,
        created_at=model.created_at,
    )


class SqlNotificationRepository(NotificationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entity_id: int) -> Notification | None:
        model = await self._session.get(NotificationModel, entity_id)
        return notification_to_entity(model) if model else None

    async def add(self, entity: Notification) -> Notification:
        model = NotificationModel(
            user_id=entity.user_id,
            chat_id=entity.chat_id,
            type=entity.type.value,
            sender_id=entity.sender_id,
            message_id=entity.message_id,
            invite_id=entity.invite_id,
            chat_title=entity.chat_title,
            preview=entity.preview,
            is_read=entity.is_read,
            created_at=entity.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        return notification_to_entity(model)

    async def delete(self, entity: Notification) -> None:
        model = await self._session.get(NotificationModel, entity.id)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()

    async def list_for_user(
        self, user_id: int, before_id: int | None, limit: int
    ) -> list[Notification]:
        stmt = select(NotificationModel).where(NotificationModel.user_id == user_id)
        if before_id is not None:
            stmt = stmt.where(NotificationModel.id < before_id)
        stmt = stmt.order_by(NotificationModel.id.desc()).limit(limit)
        models = (await self._session.scalars(stmt)).all()
        return [notification_to_entity(m) for m in models]

    async def unread_count(self, user_id: int) -> int:
        stmt = select(func.count()).select_from(NotificationModel).where(
            NotificationModel.user_id == user_id, NotificationModel.is_read.is_(False)
        )
        return (await self._session.scalar(stmt)) or 0

    async def mark_read(self, user_id: int, chat_id: int | None) -> int:
        stmt = (
            update(NotificationModel)
            .where(
                NotificationModel.user_id == user_id,
                NotificationModel.is_read.is_(False),
            )
            .values(is_read=True)
        )
        if chat_id is not None:
            stmt = stmt.where(NotificationModel.chat_id == chat_id)
        result = await self._session.execute(stmt)
        return result.rowcount or 0
