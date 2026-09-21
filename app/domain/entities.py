from dataclasses import dataclass
from datetime import datetime

from app.domain.exceptions import ValidationError
from app.domain.value_objects import (
    ArtifactKind,
    ChatType,
    InviteStatus,
    MemberRole,
    Phone,
    Username,
)


@dataclass
class User:
    id: int
    username: Username
    phone: Phone | None
    email: str | None
    first_name: str
    last_name: str | None
    bio: str | None
    avatar_path: str | None
    created_at: datetime


@dataclass
class Chat:
    id: int
    type: ChatType
    title: str | None
    description: str | None
    is_public: bool
    owner_id: int
    created_at: datetime

    def __post_init__(self) -> None:
        if self.type is ChatType.PRIVATE:
            if self.title is not None:
                raise ValidationError("private chats cannot have a title")
            if self.is_public:
                raise ValidationError("private chats cannot be public")
        elif self.title is None or not self.title.strip():
            raise ValidationError("group chats require a title")


@dataclass
class ChatMember:
    id: int
    chat_id: int
    user_id: int
    role: MemberRole
    joined_at: datetime
    invited_by_id: int | None = None


@dataclass
class Message:
    id: int
    chat_id: int
    sender_id: int
    text: str | None
    reply_to_id: int | None
    edited_at: datetime | None
    deleted_at: datetime | None
    created_at: datetime

    def attach_reply(self, reply_to: "Message") -> None:
        if reply_to.chat_id != self.chat_id:
            raise ValidationError("reply target must belong to the same chat")
        self.reply_to_id = reply_to.id


@dataclass
class Artifact:
    id: int
    message_id: int
    kind: ArtifactKind
    file_name: str
    file_path: str
    mime_type: str
    size_bytes: int
    created_at: datetime


@dataclass
class Invite:
    id: int
    chat_id: int
    inviter_id: int
    invitee_id: int | None
    token: str | None
    status: InviteStatus
    expires_at: datetime | None
    created_at: datetime

    def accept(self) -> None:
        if self.status is not InviteStatus.PENDING:
            raise ValidationError("invite is not pending")
        self.status = InviteStatus.ACCEPTED

    def decline(self) -> None:
        if self.status is not InviteStatus.PENDING:
            raise ValidationError("invite is not pending")
        self.status = InviteStatus.DECLINED

    def expire_if_needed(self, now: datetime) -> None:
        if self.status is InviteStatus.PENDING and self.expires_at is not None:
            if now >= self.expires_at:
                self.status = InviteStatus.EXPIRED


@dataclass
class Contact:
    id: int
    owner_id: int
    contact_id: int
    created_at: datetime
    name: str | None = None


@dataclass
class Block:
    id: int
    blocker_id: int
    blocked_id: int
    created_at: datetime


@dataclass
class OtpCode:
    id: int
    identifier: str
    code_hash: str
    purpose: str
    expires_at: datetime
    used_at: datetime | None
    created_at: datetime


@dataclass
class RefreshSession:
    id: int
    user_id: int
    token_hash: str
    expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime
