from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Chat, ChatMember, Invite
from app.domain.repositories.chat import ChatMemberRepository, ChatRepository, InviteRepository
from app.domain.value_objects import ChatType, InviteStatus, MemberRole
from app.infrastructure.db.models import (
    ArtifactModel,
    ChatMemberModel,
    ChatModel,
    InviteModel,
    MessageModel,
)


def chat_to_entity(model: ChatModel) -> Chat:
    return Chat(
        id=model.id,
        type=ChatType(model.type),
        title=model.title,
        description=model.description,
        is_public=model.is_public,
        owner_id=model.owner_id,
        created_at=model.created_at,
    )


class SqlChatRepository(ChatRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entity_id: int) -> Chat | None:
        model = await self._session.get(ChatModel, entity_id)
        return chat_to_entity(model) if model else None

    async def find_private_chat(self, user_a: int, user_b: int) -> Chat | None:
        model = await self._session.scalar(
            select(ChatModel)
            .where(
                ChatModel.type == "private",
                ChatModel.id.in_(
                    select(ChatMemberModel.chat_id).where(ChatMemberModel.user_id == user_a)
                ),
                ChatModel.id.in_(
                    select(ChatMemberModel.chat_id).where(ChatMemberModel.user_id == user_b)
                ),
            )
            .limit(1)
        )
        return chat_to_entity(model) if model else None

    async def list_for_user(self, user_id: int) -> list[Chat]:
        models = (
            await self._session.scalars(
                select(ChatModel)
                .join(ChatMemberModel, ChatMemberModel.chat_id == ChatModel.id)
                .where(ChatMemberModel.user_id == user_id)
                .order_by(ChatModel.id.desc())
            )
        ).all()
        return [chat_to_entity(m) for m in models]

    async def list_by_ids(self, chat_ids: Sequence[int]) -> list[Chat]:
        if not chat_ids:
            return []
        models = (
            await self._session.scalars(
                select(ChatModel).where(ChatModel.id.in_(list(chat_ids)))
            )
        ).all()
        return [chat_to_entity(m) for m in models]

    async def add(self, entity: Chat) -> Chat:
        model = ChatModel(
            type=entity.type.value,
            title=entity.title,
            description=entity.description,
            is_public=entity.is_public,
            owner_id=entity.owner_id,
            created_at=entity.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        return chat_to_entity(model)

    async def update(self, entity: Chat) -> Chat:
        model = await self._session.get(ChatModel, entity.id)
        if model is None:
            return await self.add(entity)
        model.type = entity.type.value
        model.title = entity.title
        model.description = entity.description
        model.is_public = entity.is_public
        model.owner_id = entity.owner_id
        await self._session.flush()
        return chat_to_entity(model)

    async def delete_with_contents(self, chat_id: int) -> None:
        message_ids = select(MessageModel.id).where(MessageModel.chat_id == chat_id)
        await self._session.execute(
            delete(ArtifactModel).where(ArtifactModel.message_id.in_(message_ids))
        )
        await self._session.execute(delete(MessageModel).where(MessageModel.chat_id == chat_id))
        await self._session.execute(delete(InviteModel).where(InviteModel.chat_id == chat_id))
        await self._session.execute(
            delete(ChatMemberModel).where(ChatMemberModel.chat_id == chat_id)
        )
        await self._session.execute(delete(ChatModel).where(ChatModel.id == chat_id))
        await self._session.flush()

    async def delete(self, entity: Chat) -> None:
        await self.delete_with_contents(entity.id)


def member_to_entity(model: ChatMemberModel) -> ChatMember:
    return ChatMember(
        id=model.id,
        chat_id=model.chat_id,
        user_id=model.user_id,
        role=MemberRole(model.role),
        joined_at=model.joined_at,
        invited_by_id=model.invited_by_id,
    )


class SqlChatMemberRepository(ChatMemberRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entity_id: int) -> ChatMember | None:
        model = await self._session.get(ChatMemberModel, entity_id)
        return member_to_entity(model) if model else None

    async def get_pair(self, chat_id: int, user_id: int) -> ChatMember | None:
        model = await self._session.scalar(
            select(ChatMemberModel).where(
                ChatMemberModel.chat_id == chat_id, ChatMemberModel.user_id == user_id
            )
        )
        return member_to_entity(model) if model else None

    async def list_by_chat(self, chat_id: int) -> list[ChatMember]:
        models = (
            await self._session.scalars(
                select(ChatMemberModel)
                .where(ChatMemberModel.chat_id == chat_id)
                .order_by(ChatMemberModel.joined_at, ChatMemberModel.id)
            )
        ).all()
        return [member_to_entity(m) for m in models]

    async def add(self, entity: ChatMember) -> ChatMember:
        model = ChatMemberModel(
            chat_id=entity.chat_id,
            user_id=entity.user_id,
            role=entity.role.value,
            joined_at=entity.joined_at,
            invited_by_id=entity.invited_by_id,
        )
        self._session.add(model)
        await self._session.flush()
        return member_to_entity(model)

    async def update(self, entity: ChatMember) -> ChatMember:
        model = await self._session.get(ChatMemberModel, entity.id)
        if model is None:
            return await self.add(entity)
        model.role = entity.role.value
        model.invited_by_id = entity.invited_by_id
        await self._session.flush()
        return member_to_entity(model)

    async def remove(self, chat_id: int, user_id: int) -> None:
        await self._session.execute(
            delete(ChatMemberModel).where(
                ChatMemberModel.chat_id == chat_id, ChatMemberModel.user_id == user_id
            )
        )
        await self._session.flush()

    async def delete(self, entity: ChatMember) -> None:
        await self.remove(entity.chat_id, entity.user_id)


def invite_to_entity(model: InviteModel) -> Invite:
    return Invite(
        id=model.id,
        chat_id=model.chat_id,
        inviter_id=model.inviter_id,
        invitee_id=model.invitee_id,
        token=model.token,
        status=InviteStatus(model.status),
        expires_at=model.expires_at,
        created_at=model.created_at,
    )


class SqlInviteRepository(InviteRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entity_id: int) -> Invite | None:
        model = await self._session.get(InviteModel, entity_id)
        return invite_to_entity(model) if model else None

    async def get_by_token(self, token: str) -> Invite | None:
        model = await self._session.scalar(select(InviteModel).where(InviteModel.token == token))
        return invite_to_entity(model) if model else None

    async def get_pending(self, chat_id: int, invitee_id: int) -> Invite | None:
        model = await self._session.scalar(
            select(InviteModel)
            .where(
                InviteModel.chat_id == chat_id,
                InviteModel.invitee_id == invitee_id,
                InviteModel.status == "pending",
            )
            .limit(1)
        )
        return invite_to_entity(model) if model else None

    async def list_pending_for_invitee(self, invitee_id: int) -> list[Invite]:
        models = (
            await self._session.scalars(
                select(InviteModel)
                .where(
                    InviteModel.invitee_id == invitee_id, InviteModel.status == "pending"
                )
                .order_by(InviteModel.id.desc())
            )
        ).all()
        return [invite_to_entity(m) for m in models]

    async def add(self, entity: Invite) -> Invite:
        model = InviteModel(
            chat_id=entity.chat_id,
            inviter_id=entity.inviter_id,
            invitee_id=entity.invitee_id,
            token=entity.token,
            status=entity.status.value,
            expires_at=entity.expires_at,
            created_at=entity.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        return invite_to_entity(model)

    async def update(self, entity: Invite) -> Invite:
        model = await self._session.get(InviteModel, entity.id)
        if model is None:
            return await self.add(entity)
        model.status = entity.status.value
        model.expires_at = entity.expires_at
        await self._session.flush()
        return invite_to_entity(model)

    async def delete(self, entity: Invite) -> None:
        model = await self._session.get(InviteModel, entity.id)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()
