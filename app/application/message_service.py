from app.domain.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.domain.pagination import validate_limit
from app.domain.repositories.chat import ChatMemberRepository, ChatRepository
from app.domain.repositories.contact import BlockRepository
from app.domain.repositories.user import UserRepository
from app.domain.time import utcnow
from app.domain.value_objects import ChatType
from app.domain.entities import Artifact, Chat, Message, Reaction, User
from app.domain.repositories.message import ArtifactRepository, MessageRepository, ReactionRepository
from app.domain.value_objects import ChatType, ReactionCode

class MessageService:
    def __init__(
        self,
        messages: MessageRepository,
        artifacts: ArtifactRepository,
        chats: ChatRepository,
        members: ChatMemberRepository,
        users: UserRepository,
        blocks: BlockRepository,
        reactions: ReactionRepository,
    ) -> None:
        self._messages = messages
        self._artifacts = artifacts
        self._chats = chats
        self._members = members
        self._users = users
        self._blocks = blocks
        self._reactions = reactions

    async def _require_membership(self, chat_id: int, actor_id: int) -> Chat:
        chat = await self._chats.get(chat_id)
        if chat is None:
            raise NotFoundError("chat not found")
        member = await self._members.get_pair(chat_id, actor_id)
        if member is None:
            raise ForbiddenError("you are not a member of this chat")
        return chat

    async def _ensure_can_message(self, chat: Chat, actor_id: int) -> None:
        if chat.type is ChatType.PRIVATE:
            other = [
                m.user_id
                for m in await self._members.list_by_chat(chat.id)
                if m.user_id != actor_id
            ]
            if other and await self._blocks.blocks_either(actor_id, other[0]):
                raise ForbiddenError("you cannot message this user")

    async def resolve_reply(self, chat_id: int, reply_to_id: int | None) -> int | None:
        if reply_to_id is None:
            return None
        target = await self._messages.get(reply_to_id)
        if target is None:
            raise NotFoundError("reply target not found")
        if target.chat_id != chat_id:
            raise ValidationError("reply target must belong to the same chat")
        return reply_to_id

    async def list_messages(
        self, actor_id: int, chat_id: int, before_id: int | None, limit: int | None
    ) -> list[tuple[Message, User | None, Artifact | None]]:
        await self._require_membership(chat_id, actor_id)
        limit = validate_limit(limit)
        if before_id is not None:
            cursor = await self._messages.get(before_id)
            if cursor is None:
                raise NotFoundError("before_id message not found")
            if cursor.chat_id != chat_id:
                raise ValidationError("before_id does not belong to this chat")
        page = await self._messages.list_page(chat_id, before_id, limit)
        if not page:
            return []
        senders = await self._users.list_by_ids({m.sender_id for m in page})
        sender_by_id = {u.id: u for u in senders}
        artifacts = await self._artifacts.list_by_message_ids([m.id for m in page])
        artifact_by_message = {a.message_id: a for a in artifacts}
        return [
            (m, sender_by_id.get(m.sender_id), artifact_by_message.get(m.id)) for m in page
        ]

    async def build_reply_previews(
        self, messages: list[Message]
    ) -> dict[int, tuple[Message, User | None, Artifact | None]]:
        """Reply targets (with sender and artifact) keyed by target message id."""
        ids = {m.reply_to_id for m in messages if m.reply_to_id is not None}
        if not ids:
            return {}
        targets = await self._messages.list_by_ids(list(ids))
        senders = await self._users.list_by_ids({t.sender_id for t in targets})
        sender_by_id = {u.id: u for u in senders}
        artifacts = await self._artifacts.list_by_message_ids([t.id for t in targets])
        artifact_by_message = {a.message_id: a for a in artifacts}
        return {
            t.id: (t, sender_by_id.get(t.sender_id), artifact_by_message.get(t.id))
            for t in targets
        }

    async def send_message(
        self, actor_id: int, chat_id: int, text: str | None, reply_to_id: int | None
    ) -> Message:
        chat = await self._require_membership(chat_id, actor_id)
        if text is None or not text.strip():
            raise ValidationError("message must have text or an artifact")
        await self._ensure_can_message(chat, actor_id)
        resolved_reply = await self.resolve_reply(chat_id, reply_to_id)
        message = Message(
            id=0,
            chat_id=chat_id,
            sender_id=actor_id,
            text=text,
            reply_to_id=resolved_reply,
            edited_at=None,
            deleted_at=None,
            created_at=utcnow(),
        )
        return await self._messages.add(message)

    async def edit_message(self, actor_id: int, message_id: int, text: str) -> Message:
        message = await self._messages.get(message_id)
        if message is None:
            raise NotFoundError("message not found")
        if message.sender_id != actor_id:
            raise ForbiddenError("only the sender can edit this message")
        if message.deleted_at is not None:
            raise ValidationError("cannot edit a deleted message")
        if not text.strip():
            raise ValidationError("text cannot be empty")
        message.text = text
        message.edited_at = utcnow()
        return await self._messages.update(message)

    async def delete_message(self, actor_id: int, message_id: int) -> None:
        message = await self._messages.get(message_id)
        if message is None:
            raise NotFoundError("message not found")
        if message.sender_id != actor_id:
            raise ForbiddenError("only the sender can delete this message")
        message.text = None
        message.deleted_at = utcnow()
        await self._messages.update(message)

    async def _get_reactable(self, actor_id: int, message_id: int) -> Message:
        message = await self._messages.get(message_id)
        if message is None:
            raise NotFoundError("message not found")
        chat = await self._require_membership(message.chat_id, actor_id)
        if message.deleted_at is not None:
            raise ValidationError("cannot react to a deleted message")
        await self._ensure_can_message(chat, actor_id)
        return message

    async def set_reaction(self, actor_id: int, message_id: int, code: str) -> Message:
        reaction_code = ReactionCode.parse(code)
        message = await self._get_reactable(actor_id, message_id)
        existing = await self._reactions.get_pair(message.id, actor_id)
        if existing is None:
            await self._reactions.add(
                Reaction(
                    id=0,
                    message_id=message.id,
                    user_id=actor_id,
                    code=reaction_code,
                    created_at=utcnow(),
                )
            )
        elif existing.code is not reaction_code:
            existing.code = reaction_code
            await self._reactions.update(existing)
        return message

    async def remove_reaction(self, actor_id: int, message_id: int) -> Message:
        message = await self._get_reactable(actor_id, message_id)
        existing = await self._reactions.get_pair(message.id, actor_id)
        if existing is not None:
            await self._reactions.delete(existing)
        return message

    async def build_reactions(self, messages: list[Message]) -> dict[int, list[Reaction]]:
        grouped: dict[int, list[Reaction]] = {}
        for reaction in await self._reactions.list_by_message_ids([m.id for m in messages]):
            grouped.setdefault(reaction.message_id, []).append(reaction)
        return grouped
