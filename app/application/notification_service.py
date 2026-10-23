from app.domain.entities import Artifact, Invite, Message, Notification
from app.domain.exceptions import NotFoundError, ValidationError
from app.domain.pagination import validate_limit
from app.domain.repositories.chat import ChatMemberRepository, ChatRepository
from app.domain.repositories.notification import NotificationRepository
from app.domain.repositories.user import UserRepository
from app.domain.time import utcnow
from app.domain.value_objects import ChatType, NotificationType

PREVIEW_MAX_CHARS = 120


class NotificationService:
    def __init__(
        self,
        notifications: NotificationRepository,
        members: ChatMemberRepository,
        users: UserRepository,
        chats: ChatRepository,
    ) -> None:
        self._notifications = notifications
        self._members = members
        self._users = users
        self._chats = chats

    @staticmethod
    def _message_preview(message: Message, artifact: Artifact | None) -> str:
        if message.text:
            text = message.text.strip()
            if len(text) > PREVIEW_MAX_CHARS:
                return text[:PREVIEW_MAX_CHARS] + "…"
            return text
        if artifact is not None:
            return f"sent {artifact.file_name}"
        return "sent a message"

    async def notify_message(
        self, message: Message, artifact: Artifact | None = None
    ) -> list[Notification]:
        """One notification row per chat member except the sender."""
        chat = await self._chats.get(message.chat_id)
        if chat is None:
            raise NotFoundError("chat not found")
        recipients = [
            m.user_id
            for m in await self._members.list_by_chat(message.chat_id)
            if m.user_id != message.sender_id
        ]
        preview = self._message_preview(message, artifact)
        chat_title = chat.title if chat.type is ChatType.GROUP else None
        created = []
        for user_id in recipients:
            created.append(
                await self._notifications.add(
                    Notification(
                        id=0,
                        user_id=user_id,
                        chat_id=message.chat_id,
                        type=NotificationType.MESSAGE,
                        sender_id=message.sender_id,
                        message_id=message.id,
                        invite_id=None,
                        chat_title=chat_title,
                        preview=preview,
                        is_read=False,
                        created_at=utcnow(),
                    )
                )
            )
        return created

    async def notify_invite(self, invite: Invite) -> Notification:
        chat = await self._chats.get(invite.chat_id)
        if chat is None:
            raise NotFoundError("chat not found")
        if invite.invitee_id is None:
            raise ValidationError("link invites do not target a single user")
        return await self._notifications.add(
            Notification(
                id=0,
                user_id=invite.invitee_id,
                chat_id=invite.chat_id,
                type=NotificationType.INVITE,
                sender_id=invite.inviter_id,
                message_id=None,
                invite_id=invite.id,
                chat_title=chat.title,
                preview=f"invited you to {chat.title}",
                is_read=False,
                created_at=utcnow(),
            )
        )

    async def build_dtos(self, notifications: list[Notification]) -> list[dict]:
        sender_ids = {n.sender_id for n in notifications}
        senders = await self._users.list_by_ids(list(sender_ids))
        username_by_id = {u.id: str(u.username) for u in senders}
        return [
            {
                "id": n.id,
                "type": n.type.value,
                "chat_id": n.chat_id,
                "chat_title": n.chat_title,
                "sender_id": n.sender_id,
                "sender_username": username_by_id.get(n.sender_id),
                "preview": n.preview,
                "message_id": n.message_id,
                "invite_id": n.invite_id,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifications
        ]

    async def list_for_user(
        self, user_id: int, before_id: int | None, limit: int | None
    ) -> list[dict]:
        limit = validate_limit(limit)
        page = await self._notifications.list_for_user(user_id, before_id, limit)
        return await self.build_dtos(page)

    async def unread_count(self, user_id: int) -> int:
        return await self._notifications.unread_count(user_id)

    async def mark_read(self, user_id: int, chat_id: int | None) -> int:
        await self._notifications.mark_read(user_id, chat_id)
        return await self._notifications.unread_count(user_id)
