from datetime import datetime

from pydantic import BaseModel

from app.domain.entities import Artifact, Chat, ChatMember, Message, Reaction, User
from app.domain.value_objects import ReactionCode

class UserPublic(BaseModel):
    id: int
    username: str
    first_name: str
    last_name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    created_at: datetime


def user_to_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        username=str(user.username),
        first_name=user.first_name,
        last_name=user.last_name,
        bio=user.bio,
        avatar_url=f"/media/{user.avatar_path}" if user.avatar_path else None,
        created_at=user.created_at,
    )


class MemberOut(BaseModel):
    user_id: int
    username: str
    first_name: str
    last_name: str | None = None
    role: str
    joined_at: datetime


def member_to_out(member: ChatMember, user: User) -> MemberOut:
    return MemberOut(
        user_id=user.id,
        username=str(user.username),
        first_name=user.first_name,
        last_name=user.last_name,
        role=member.role.value,
        joined_at=member.joined_at,
    )


class ChatOut(BaseModel):
    id: int
    type: str
    title: str | None = None
    description: str | None = None
    is_public: bool
    owner_id: int
    created_at: datetime


def chat_to_out(chat: Chat) -> ChatOut:
    return ChatOut(
        id=chat.id,
        type=chat.type.value,
        title=chat.title,
        description=chat.description,
        is_public=chat.is_public,
        owner_id=chat.owner_id,
        created_at=chat.created_at,
    )


class ArtifactOut(BaseModel):
    id: int
    kind: str
    file_name: str
    mime_type: str
    size_bytes: int
    url: str


def artifact_to_out(artifact: Artifact) -> ArtifactOut:
    return ArtifactOut(
        id=artifact.id,
        kind=artifact.kind.value,
        file_name=artifact.file_name,
        mime_type=artifact.mime_type,
        size_bytes=artifact.size_bytes,
        url=f"/media/{artifact.file_path}",
    )

class ReactionOut(BaseModel):
    code: str
    count: int
    user_ids: list[int]


def reactions_to_out(reactions: list[Reaction]) -> list[ReactionOut]:
    users_by_code: dict[ReactionCode, list[int]] = {}
    for reaction in reactions:
        users_by_code.setdefault(reaction.code, []).append(reaction.user_id)
    return [
        ReactionOut(code=code.value, count=len(user_ids), user_ids=user_ids)
        for code, user_ids in users_by_code.items()
    ]

class ReplyPreview(BaseModel):
    id: int
    sender_username: str
    text: str | None = None
    file_name: str | None = None
    deleted: bool = False


class MessageOut(BaseModel):
    id: int
    chat_id: int
    sender: UserPublic
    text: str | None = None
    reply_to_id: int | None = None
    reply_to: ReplyPreview | None = None
    artifact: ArtifactOut | None = None
    created_at: datetime
    edited_at: datetime | None = None
    deleted_at: datetime | None = None
    reactions: list[ReactionOut] = []


def reply_preview_to_out(
    target: Message, sender: User | None, artifact: Artifact | None
) -> ReplyPreview:
    return ReplyPreview(
        id=target.id,
        sender_username=str(sender.username) if sender else "unknown",
        text=target.text if target.deleted_at is None else None,
        file_name=artifact.file_name if artifact else None,
        deleted=target.deleted_at is not None,
    )


def message_to_out(
    message: Message,
    sender: User | None,
    artifact: Artifact | None,
    reply_to: ReplyPreview | None = None,
    reactions: list[ReactionOut] | None = None,
) -> MessageOut:
    return MessageOut(
        id=message.id,
        chat_id=message.chat_id,
        sender=user_to_public(sender) if sender else UserPublic(
            id=message.sender_id, username="unknown", first_name="unknown", created_at=message.created_at
        ),
        text=message.text,
        reply_to_id=message.reply_to_id,
        reply_to=reply_to,
        artifact=artifact_to_out(artifact) if artifact else None,
        created_at=message.created_at,
        edited_at=message.edited_at,
        deleted_at=message.deleted_at,
        reactions=[] if message.deleted_at else reactions or [],
    )


class ChatListItem(ChatOut):
    last_message: MessageOut | None = None


class ContactOut(BaseModel):
    user_id: int
    username: str
    first_name: str
    last_name: str | None = None
    avatar_url: str | None = None
    name: str | None = None


def contact_to_out(user: User, name: str | None = None) -> ContactOut:
    return ContactOut(
        user_id=user.id,
        username=str(user.username),
        first_name=user.first_name,
        last_name=user.last_name,
        avatar_url=f"/media/{user.avatar_path}" if user.avatar_path else None,
        name=name,
    )
