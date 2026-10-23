import pytest

from app.domain.entities import (
    Chat,
    ChatMember,
    Invite,
    Message,
    Notification,
    User,
)
from app.domain.exceptions import ValidationError
from app.domain.repositories.chat import ChatMemberRepository, ChatRepository
from app.domain.repositories.notification import NotificationRepository
from app.domain.repositories.user import UserRepository
from app.domain.time import utcnow
from app.domain.value_objects import (
    ChatType,
    InviteStatus,
    MemberRole,
    NotificationType,
    Username,
)


class FakeNotificationRepository(NotificationRepository):
    def __init__(self) -> None:
        self._items: dict[int, Notification] = {}
        self._next_id = 1

    async def get(self, entity_id: int) -> Notification | None:
        return self._items.get(entity_id)

    async def add(self, entity: Notification) -> Notification:
        entity.id = self._next_id
        self._next_id += 1
        self._items[entity.id] = entity
        return entity

    async def delete(self, entity: Notification) -> None:
        self._items.pop(entity.id, None)

    async def list_for_user(
        self, user_id: int, before_id: int | None, limit: int
    ) -> list[Notification]:
        rows = [n for n in self._items.values() if n.user_id == user_id]
        rows.sort(key=lambda n: n.id, reverse=True)
        if before_id is not None:
            rows = [n for n in rows if n.id < before_id]
        return rows[:limit]

    async def unread_count(self, user_id: int) -> int:
        return sum(1 for n in self._items.values() if n.user_id == user_id and not n.is_read)

    async def mark_read(self, user_id: int, chat_id: int | None) -> int:
        changed = 0
        for n in self._items.values():
            if n.user_id == user_id and not n.is_read and (chat_id is None or n.chat_id == chat_id):
                n.mark_read()
                changed += 1
        return changed


class FakeChatRepository(ChatRepository):
    def __init__(self, chat: Chat) -> None:
        self._chat = chat

    async def get(self, entity_id: int) -> Chat | None:
        return self._chat if self._chat.id == entity_id else None

    async def add(self, entity: Chat) -> Chat:
        return entity

    async def delete(self, entity: Chat) -> None:
        pass

    async def find_private_chat(self, user_a: int, user_b: int) -> Chat | None:
        return None

    async def list_for_user(self, user_id: int) -> list[Chat]:
        return []

    async def list_by_ids(self, chat_ids) -> list[Chat]:
        return [self._chat] if self._chat.id in chat_ids else []

    async def update(self, entity: Chat) -> Chat:
        return entity

    async def delete_with_contents(self, chat_id: int) -> None:
        pass


class FakeMemberRepository(ChatMemberRepository):
    def __init__(self, members: list[ChatMember]) -> None:
        self._members = members

    async def get(self, entity_id: int) -> ChatMember | None:
        return None

    async def add(self, entity: ChatMember) -> ChatMember:
        return entity

    async def delete(self, entity: ChatMember) -> None:
        pass

    async def get_pair(self, chat_id: int, user_id: int) -> ChatMember | None:
        return None

    async def list_by_chat(self, chat_id: int) -> list[ChatMember]:
        return self._members

    async def list_other_members(self, chat_ids, user_id: int) -> list[ChatMember]:
        return []

    async def remove(self, chat_id: int, user_id: int) -> None:
        pass

    async def update(self, entity: ChatMember) -> ChatMember:
        return entity


class FakeUserRepository(UserRepository):
    def __init__(self, users: list[User]) -> None:
        self._users = {u.id: u for u in users}

    async def get(self, entity_id: int) -> User | None:
        return self._users.get(entity_id)

    async def add(self, entity: User) -> User:
        return entity

    async def delete(self, entity: User) -> None:
        pass

    async def get_by_username(self, username: str) -> User | None:
        return None

    async def get_by_identifier(self, identifier: str) -> User | None:
        return None

    async def list_by_ids(self, user_ids) -> list[User]:
        return [u for uid in user_ids if (u := self._users.get(uid))]

    async def search(self, query: str) -> list[User]:
        return []

    async def update(self, entity: User) -> User:
        return entity


def _user(uid: int, name: str) -> User:
    return User(
        id=uid,
        username=Username(name),
        phone=None,
        email=None,
        first_name=name.capitalize(),
        last_name=None,
        bio=None,
        avatar_path=None,
        created_at=utcnow(),
    )


def _member(chat_id: int, user_id: int) -> ChatMember:
    return ChatMember(
        id=user_id, chat_id=chat_id, user_id=user_id, role=MemberRole.MEMBER, joined_at=utcnow()
    )


def _group(chat_id: int, title: str) -> Chat:
    return Chat(
        id=chat_id,
        type=ChatType.GROUP,
        title=title,
        description=None,
        is_public=False,
        owner_id=1,
        created_at=utcnow(),
    )


class TestNotificationType:
    @pytest.mark.parametrize("value", ["message", "invite"])
    def test_parse_valid(self, value: str) -> None:
        assert NotificationType.parse(value) is NotificationType(value)

    def test_parse_invalid(self) -> None:
        with pytest.raises(ValidationError):
            NotificationType.parse("nope")


class TestNotificationEntity:
    def test_mark_read_is_idempotent(self) -> None:
        notification = Notification(
            id=1,
            user_id=2,
            chat_id=3,
            type=NotificationType.MESSAGE,
            sender_id=4,
            message_id=5,
            invite_id=None,
            chat_title=None,
            preview="hello",
            is_read=False,
            created_at=utcnow(),
        )
        notification.mark_read()
        assert notification.is_read is True
        notification.mark_read()
        assert notification.is_read is True


class TestNotificationService:
    def _make_service(
        self,
        chat: Chat,
        members: list[ChatMember],
        users: list[User],
    ):
        from app.application.notification_service import NotificationService

        return (
            NotificationService(
                FakeNotificationRepository(),
                FakeMemberRepository(members),
                FakeUserRepository(users),
                FakeChatRepository(chat),
            ),
            chat,
        )

    async def test_notify_message_creates_rows_for_everyone_except_sender(self) -> None:
        service, chat = self._make_service(
            _group(7, "Team"),
            [_member(7, 1), _member(7, 2), _member(7, 3)],
            [_user(1, "alice"), _user(2, "bob"), _user(3, "carol")],
        )
        message = Message(
            id=10, chat_id=7, sender_id=1, text="hi team", reply_to_id=None,
            edited_at=None, deleted_at=None, created_at=utcnow(),
        )
        created = await service.notify_message(message)
        assert sorted(n.user_id for n in created) == [2, 3]
        for n in created:
            assert n.type is NotificationType.MESSAGE
            assert n.sender_id == 1
            assert n.message_id == 10
            assert n.chat_title == "Team"
            assert n.preview == "hi team"
            assert n.is_read is False

    async def test_notify_message_private_chat_has_no_title(self) -> None:
        private = Chat(
            id=8, type=ChatType.PRIVATE, title=None, description=None,
            is_public=False, owner_id=1, created_at=utcnow(),
        )
        service, _ = self._make_service(
            private, [_member(8, 1), _member(8, 2)], [_user(1, "alice"), _user(2, "bob")]
        )
        message = Message(
            id=11, chat_id=8, sender_id=1, text="psst", reply_to_id=None,
            edited_at=None, deleted_at=None, created_at=utcnow(),
        )
        created = await service.notify_message(message)
        assert len(created) == 1
        assert created[0].chat_title is None

    async def test_notify_message_trims_long_preview(self) -> None:
        service, _ = self._make_service(
            _group(7, "Team"), [_member(7, 1), _member(7, 2)], [_user(1, "alice"), _user(2, "bob")]
        )
        message = Message(
            id=12, chat_id=7, sender_id=1, text="x" * 300, reply_to_id=None,
            edited_at=None, deleted_at=None, created_at=utcnow(),
        )
        created = await service.notify_message(message)
        assert len(created[0].preview) == 121
        assert created[0].preview.endswith("…")

    async def test_notify_invite_creates_one_row_for_invitee(self) -> None:
        service, chat = self._make_service(
            _group(7, "Team"), [], [_user(1, "alice"), _user(2, "bob")]
        )
        invite = Invite(
            id=20, chat_id=7, inviter_id=1, invitee_id=2, token=None,
            status=InviteStatus.PENDING, expires_at=None, created_at=utcnow(),
        )
        created = await service.notify_invite(invite)
        assert created.user_id == 2
        assert created.type is NotificationType.INVITE
        assert created.sender_id == 1
        assert created.invite_id == 20
        assert created.preview == "invited you to Team"

    async def test_build_dtos_include_sender_username(self) -> None:
        service, _ = self._make_service(
            _group(7, "Team"), [_member(7, 1), _member(7, 2)], [_user(1, "alice"), _user(2, "bob")]
        )
        message = Message(
            id=13, chat_id=7, sender_id=1, text="yo", reply_to_id=None,
            edited_at=None, deleted_at=None, created_at=utcnow(),
        )
        created = await service.notify_message(message)
        dtos = await service.build_dtos(created)
        assert len(dtos) == 1
        dto = dtos[0]
        assert dto["type"] == "message"
        assert dto["sender_username"] == "alice"
        assert dto["chat_title"] == "Team"
        assert dto["preview"] == "yo"
        assert dto["is_read"] is False
        assert dto["message_id"] == 13
        assert dto["invite_id"] is None

    async def test_mark_read_returns_new_unread_count(self) -> None:
        service, _ = self._make_service(
            _group(7, "Team"), [_member(7, 1), _member(7, 2)], [_user(1, "alice"), _user(2, "bob")]
        )
        await service.notify_message(
            Message(
                id=14, chat_id=7, sender_id=1, text="one", reply_to_id=None,
                edited_at=None, deleted_at=None, created_at=utcnow(),
            )
        )
        await service.notify_message(
            Message(
                id=15, chat_id=7, sender_id=1, text="two", reply_to_id=None,
                edited_at=None, deleted_at=None, created_at=utcnow(),
            )
        )
        assert await service.unread_count(2) == 2
        assert await service.mark_read(2, chat_id=None) == 0
        assert await service.unread_count(2) == 0
