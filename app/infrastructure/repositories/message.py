from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Artifact, Message
from app.domain.repositories.message import ArtifactRepository, MessageRepository
from app.domain.value_objects import ArtifactKind
from app.infrastructure.db.models import ArtifactModel, MessageModel


def message_to_entity(model: MessageModel) -> Message:
    return Message(
        id=model.id,
        chat_id=model.chat_id,
        sender_id=model.sender_id,
        text=model.text,
        reply_to_id=model.reply_to_id,
        edited_at=model.edited_at,
        deleted_at=model.deleted_at,
        created_at=model.created_at,
    )


class SqlMessageRepository(MessageRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entity_id: int) -> Message | None:
        model = await self._session.get(MessageModel, entity_id)
        return message_to_entity(model) if model else None

    async def list_page(self, chat_id: int, before_id: int | None, limit: int) -> list[Message]:
        stmt = select(MessageModel).where(MessageModel.chat_id == chat_id)
        if before_id is not None:
            stmt = stmt.where(MessageModel.id < before_id)
        stmt = stmt.order_by(MessageModel.id.desc()).limit(limit)
        models = (await self._session.scalars(stmt)).all()
        return [message_to_entity(m) for m in models]

    async def last_for_chats(self, chat_ids: Sequence[int]) -> dict[int, Message]:
        if not chat_ids:
            return {}
        latest_ids = select(func.max(MessageModel.id)).where(
            MessageModel.chat_id.in_(list(chat_ids))
        ).group_by(MessageModel.chat_id)
        models = (await self._session.scalars(select(MessageModel).where(MessageModel.id.in_(latest_ids)))).all()
        return {m.chat_id: message_to_entity(m) for m in models}

    async def add(self, entity: Message) -> Message:
        model = MessageModel(
            chat_id=entity.chat_id,
            sender_id=entity.sender_id,
            reply_to_id=entity.reply_to_id,
            text=entity.text,
            edited_at=entity.edited_at,
            deleted_at=entity.deleted_at,
            created_at=entity.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        return message_to_entity(model)

    async def update(self, entity: Message) -> Message:
        model = await self._session.get(MessageModel, entity.id)
        if model is None:
            return await self.add(entity)
        model.text = entity.text
        model.reply_to_id = entity.reply_to_id
        model.edited_at = entity.edited_at
        model.deleted_at = entity.deleted_at
        await self._session.flush()
        return message_to_entity(model)

    async def delete(self, entity: Message) -> None:
        model = await self._session.get(MessageModel, entity.id)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()


def artifact_to_entity(model: ArtifactModel) -> Artifact:
    return Artifact(
        id=model.id,
        message_id=model.message_id,
        kind=ArtifactKind(model.kind),
        file_name=model.file_name,
        file_path=model.file_path,
        mime_type=model.mime_type,
        size_bytes=model.size_bytes,
        created_at=model.created_at,
    )


class SqlArtifactRepository(ArtifactRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entity_id: int) -> Artifact | None:
        model = await self._session.get(ArtifactModel, entity_id)
        return artifact_to_entity(model) if model else None

    async def list_by_message_ids(self, message_ids: Sequence[int]) -> list[Artifact]:
        if not message_ids:
            return []
        models = (
            await self._session.scalars(
                select(ArtifactModel).where(ArtifactModel.message_id.in_(list(message_ids)))
            )
        ).all()
        return [artifact_to_entity(m) for m in models]

    async def add(self, entity: Artifact) -> Artifact:
        model = ArtifactModel(
            message_id=entity.message_id,
            kind=entity.kind.value,
            file_name=entity.file_name,
            file_path=entity.file_path,
            mime_type=entity.mime_type,
            size_bytes=entity.size_bytes,
            created_at=entity.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        return artifact_to_entity(model)

    async def delete(self, entity: Artifact) -> None:
        model = await self._session.get(ArtifactModel, entity.id)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()
