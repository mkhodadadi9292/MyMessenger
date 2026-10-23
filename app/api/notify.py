from sqlalchemy.ext.asyncio import AsyncSession

from app.application.notification_service import NotificationService
from app.domain.entities import Artifact, Invite, Message
from app.infrastructure.repositories.chat import SqlChatMemberRepository, SqlChatRepository
from app.infrastructure.repositories.notification import SqlNotificationRepository
from app.infrastructure.repositories.user import SqlUserRepository
from app.infrastructure.sse import SseHub


def _service(session: AsyncSession) -> NotificationService:
    return NotificationService(
        SqlNotificationRepository(session),
        SqlChatMemberRepository(session),
        SqlUserRepository(session),
        SqlChatRepository(session),
    )


async def _push(session: AsyncSession, hub: SseHub, service: NotificationService, user_id: int, dto: dict) -> None:
    unread = await service.unread_count(user_id)
    await hub.publish(
        user_id,
        {"type": "notification.new", "notification": dto, "unread_count": unread},
    )


async def notify_new_message(
    hub: SseHub, session: AsyncSession, message: Message, artifact: Artifact | None = None
) -> None:
    """Creates inbox rows, COMMITS them, then pushes SSE events to recipients.

    Commit-before-notify: receivers refetch the inbox right after the event
    arrives, so the rows must be durable before the event is published.
    """
    service = _service(session)
    created = await service.notify_message(message, artifact)
    if not created:
        return
    dtos = await service.build_dtos(created)
    await session.commit()
    for notification, dto in zip(created, dtos, strict=True):
        await _push(session, hub, service, notification.user_id, dto)


async def notify_new_invite(hub: SseHub, session: AsyncSession, invite: Invite) -> None:
    """Creates the invitee's inbox row, COMMITS it, then pushes the SSE event."""
    service = _service(session)
    notification = await service.notify_invite(invite)
    dto = (await service.build_dtos([notification]))[0]
    await session.commit()
    await _push(session, hub, service, notification.user_id, dto)
