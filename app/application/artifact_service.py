from app.application.message_service import MessageService
from app.config import Settings
from app.domain.entities import Artifact, Message
from app.domain.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.domain.repositories.chat import ChatMemberRepository, ChatRepository
from app.domain.repositories.contact import BlockRepository
from app.domain.repositories.message import ArtifactRepository, MessageRepository
from app.domain.repositories.user import UserRepository
from app.domain.time import utcnow
from app.domain.value_objects import ArtifactKind, ChatType
from app.infrastructure.storage import LocalStorage


class ArtifactService:
    def __init__(
        self,
        messages: MessageRepository,
        artifacts: ArtifactRepository,
        chats: ChatRepository,
        members: ChatMemberRepository,
        users: UserRepository,
        blocks: BlockRepository,
        storage: LocalStorage,
        settings: Settings,
    ) -> None:
        self._messages = messages
        self._artifacts = artifacts
        self._chats = chats
        self._members = members
        self._users = users
        self._blocks = blocks
        self._storage = storage
        self._settings = settings
        self._message_service = MessageService(
            messages, artifacts, chats, members, users, blocks
        )

    async def upload(
        self,
        actor_id: int,
        chat_id: int,
        kind: ArtifactKind,
        file_name: str,
        mime_type: str,
        content: bytes,
        reply_to_id: int | None,
    ) -> tuple[Message, Artifact]:
        chat = await self._chats.get(chat_id)
        if chat is None:
            raise NotFoundError("chat not found")
        member = await self._members.get_pair(chat_id, actor_id)
        if member is None:
            raise ForbiddenError("you are not a member of this chat")
        if not kind.accepts_mime(mime_type):
            raise ValidationError(f"mime type {mime_type} is not valid for {kind.value}")
        max_bytes = self._settings.max_artifact_size_mb * 1024 * 1024
        if len(content) > max_bytes:
            raise ValidationError("artifact is too large")
        if chat.type is ChatType.PRIVATE:
            other = [
                m.user_id for m in await self._members.list_by_chat(chat_id) if m.user_id != actor_id
            ]
            if other and await self._blocks.blocks_either(actor_id, other[0]):
                raise ForbiddenError("you cannot message this user")
        resolved_reply = await self._message_service.resolve_reply(chat_id, reply_to_id)
        message = Message(
            id=0,
            chat_id=chat_id,
            sender_id=actor_id,
            text=None,
            reply_to_id=resolved_reply,
            edited_at=None,
            deleted_at=None,
            created_at=utcnow(),
        )
        created_message = await self._messages.add(message)
        relative = self._storage.save("artifacts", file_name, content)
        artifact = Artifact(
            id=0,
            message_id=created_message.id,
            kind=kind,
            file_name=file_name,
            file_path=relative,
            mime_type=mime_type,
            size_bytes=len(content),
            created_at=utcnow(),
        )
        created_artifact = await self._artifacts.add(artifact)
        return created_message, created_artifact

    async def download(self, actor_id: int, artifact_id: int) -> tuple[Artifact, str]:
        artifact = await self._artifacts.get(artifact_id)
        if artifact is None:
            raise NotFoundError("artifact not found")
        message = await self._messages.get(artifact.message_id)
        if message is None:
            raise NotFoundError("artifact not found")
        member = await self._members.get_pair(message.chat_id, actor_id)
        if member is None:
            raise ForbiddenError("you are not a member of this chat")
        return artifact, str(self._storage.path_for(artifact.file_path))
