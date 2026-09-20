from datetime import datetime, timedelta, timezone

import pytest

from app.domain.entities import Chat, Invite, Message
from app.domain.exceptions import ValidationError
from app.domain.value_objects import ChatType, InviteStatus

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_chat(**overrides) -> Chat:
    defaults = dict(
        id=1,
        type=ChatType.GROUP,
        title="g",
        description=None,
        is_public=False,
        owner_id=1,
        created_at=NOW,
    )
    return Chat(**(defaults | overrides))


def make_message(chat_id: int = 1, **overrides) -> Message:
    defaults = dict(
        id=1,
        chat_id=chat_id,
        sender_id=1,
        text="hi",
        reply_to_id=None,
        edited_at=None,
        deleted_at=None,
        created_at=NOW,
    )
    return Message(**(defaults | overrides))


def make_invite(**overrides) -> Invite:
    defaults = dict(
        id=1,
        chat_id=1,
        inviter_id=1,
        invitee_id=2,
        token=None,
        status=InviteStatus.PENDING,
        expires_at=None,
        created_at=NOW,
    )
    return Invite(**(defaults | overrides))


class TestChat:
    def test_private_chat_has_no_title(self) -> None:
        with pytest.raises(ValidationError):
            make_chat(type=ChatType.PRIVATE, title="oops", is_public=False)

    def test_private_chat_cannot_be_public(self) -> None:
        with pytest.raises(ValidationError):
            make_chat(type=ChatType.PRIVATE, title=None, is_public=True)

    def test_group_requires_title(self) -> None:
        with pytest.raises(ValidationError):
            make_chat(title=None)

    def test_valid_group(self) -> None:
        chat = make_chat(title="Team", is_public=True)
        assert chat.type is ChatType.GROUP
        assert chat.is_public is True

    def test_valid_private_chat(self) -> None:
        chat = make_chat(type=ChatType.PRIVATE, title=None, is_public=False)
        assert chat.type is ChatType.PRIVATE


class TestMessage:
    def test_attach_reply_same_chat(self) -> None:
        message = make_message(id=2, chat_id=1)
        message.attach_reply(make_message(id=1, chat_id=1))
        assert message.reply_to_id == 1

    def test_attach_reply_different_chat_raises(self) -> None:
        message = make_message(id=2, chat_id=1)
        with pytest.raises(ValidationError):
            message.attach_reply(make_message(id=1, chat_id=2))


class TestInvite:
    def test_accept_pending(self) -> None:
        invite = make_invite()
        invite.accept()
        assert invite.status is InviteStatus.ACCEPTED

    def test_accept_twice_raises(self) -> None:
        invite = make_invite()
        invite.accept()
        with pytest.raises(ValidationError):
            invite.accept()

    def test_decline_pending(self) -> None:
        invite = make_invite()
        invite.decline()
        assert invite.status is InviteStatus.DECLINED

    def test_accept_after_decline_raises(self) -> None:
        invite = make_invite()
        invite.decline()
        with pytest.raises(ValidationError):
            invite.accept()

    def test_decline_twice_raises(self) -> None:
        invite = make_invite()
        invite.decline()
        with pytest.raises(ValidationError):
            invite.decline()

    def test_expired_invite_cannot_be_accepted(self) -> None:
        invite = make_invite(expires_at=NOW + timedelta(minutes=5))
        invite.expire_if_needed(NOW + timedelta(minutes=6))
        assert invite.status is InviteStatus.EXPIRED
        with pytest.raises(ValidationError):
            invite.accept()

    def test_expire_if_needed_keeps_valid(self) -> None:
        invite = make_invite(expires_at=NOW + timedelta(minutes=5))
        invite.expire_if_needed(NOW)
        assert invite.status is InviteStatus.PENDING

    def test_expire_if_needed_without_expiry(self) -> None:
        invite = make_invite()
        invite.expire_if_needed(NOW)
        assert invite.status is InviteStatus.PENDING
