from app.domain.entities import Artifact, Chat, ChatMember, Invite, Message, User
from app.domain.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.domain.permissions import can_edit_chat, can_invite, can_promote, can_remove_member
from app.domain.repositories.chat import ChatMemberRepository, ChatRepository, InviteRepository
from app.domain.repositories.message import ArtifactRepository, MessageRepository
from app.domain.repositories.user import UserRepository
from app.domain.time import utcnow
from app.domain.value_objects import ChatType, InviteStatus, MemberRole


class ChatService:
    def __init__(
        self,
        chats: ChatRepository,
        members: ChatMemberRepository,
        invites: InviteRepository,
        messages: MessageRepository,
        artifacts: ArtifactRepository,
        users: UserRepository,
    ) -> None:
        self._chats = chats
        self._members = members
        self._invites = invites
        self._messages = messages
        self._artifacts = artifacts
        self._users = users

    async def _get_chat(self, chat_id: int) -> Chat:
        chat = await self._chats.get(chat_id)
        if chat is None:
            raise NotFoundError("chat not found")
        return chat

    async def _require_member(self, chat_id: int, user_id: int) -> ChatMember:
        member = await self._members.get_pair(chat_id, user_id)
        if member is None:
            raise ForbiddenError("you are not a member of this chat")
        return member

    async def list_chats(
        self, user_id: int
    ) -> list[tuple[Chat, Message | None, User | None, Artifact | None]]:
        chats = await self._chats.list_for_user(user_id)
        last = await self._messages.last_for_chats([c.id for c in chats])
        senders = await self._users.list_by_ids({m.sender_id for m in last.values()})
        sender_by_id = {u.id: u for u in senders}
        artifacts = await self._artifacts.list_by_message_ids([m.id for m in last.values()])
        artifact_by_message = {a.message_id: a for a in artifacts}
        ordered = sorted(
            chats,
            key=lambda c: (
                last[c.id].created_at if c.id in last else c.created_at,
                c.id,
            ),
            reverse=True,
        )
        return [
            (
                c,
                last.get(c.id),
                sender_by_id.get(last[c.id].sender_id) if c.id in last else None,
                artifact_by_message.get(last[c.id].id) if c.id in last else None,
            )
            for c in ordered
        ]

    async def open_private_chat(self, actor_id: int, target_id: int) -> Chat:
        if actor_id == target_id:
            raise ValidationError("cannot open a private chat with yourself")
        target = await self._users.get(target_id)
        if target is None:
            raise NotFoundError("user not found")
        existing = await self._chats.find_private_chat(actor_id, target_id)
        if existing is not None:
            return existing
        now = utcnow()
        chat = Chat(
            id=0,
            type=ChatType.PRIVATE,
            title=None,
            description=None,
            is_public=False,
            owner_id=actor_id,
            created_at=now,
        )
        created = await self._chats.add(chat)
        await self._members.add(
            ChatMember(id=0, chat_id=created.id, user_id=actor_id, role=MemberRole.MEMBER, joined_at=now)
        )
        await self._members.add(
            ChatMember(id=0, chat_id=created.id, user_id=target_id, role=MemberRole.MEMBER, joined_at=now)
        )
        return created

    async def create_group(
        self, actor_id: int, title: str, description: str | None, is_public: bool
    ) -> Chat:
        now = utcnow()
        chat = Chat(
            id=0,
            type=ChatType.GROUP,
            title=title,
            description=description,
            is_public=is_public,
            owner_id=actor_id,
            created_at=now,
        )
        created = await self._chats.add(chat)
        await self._members.add(
            ChatMember(id=0, chat_id=created.id, user_id=actor_id, role=MemberRole.OWNER, joined_at=now)
        )
        return created

    async def get_chat(self, actor_id: int, chat_id: int) -> Chat:
        chat = await self._get_chat(chat_id)
        await self._require_member(chat_id, actor_id)
        return chat

    async def update_chat(
        self, actor_id: int, chat_id: int, title: str | None, description: str | None
    ) -> Chat:
        chat = await self._get_chat(chat_id)
        actor = await self._require_member(chat_id, actor_id)
        if not can_edit_chat(actor.role):
            raise ForbiddenError("only admins can edit the chat")
        if title is not None:
            chat.title = title
        if description is not None:
            chat.description = description
        return await self._chats.update(chat)

    async def list_members(self, actor_id: int, chat_id: int) -> list[tuple[ChatMember, User]]:
        await self._get_chat(chat_id)
        await self._require_member(chat_id, actor_id)
        entries = await self._members.list_by_chat(chat_id)
        users = await self._users.list_by_ids([m.user_id for m in entries])
        by_id = {u.id: u for u in users}
        return [(m, by_id[m.user_id]) for m in entries if m.user_id in by_id]

    async def add_member(self, actor_id: int, chat_id: int, target_id: int) -> dict:
        chat = await self._get_chat(chat_id)
        actor = await self._require_member(chat_id, actor_id)
        if not can_invite(actor.role):
            raise ForbiddenError("only admins can add members")
        if chat.type is not ChatType.GROUP:
            raise ValidationError("cannot add members to a private chat")
        target = await self._users.get(target_id)
        if target is None:
            raise NotFoundError("user not found")
        if await self._members.get_pair(chat_id, target_id) is not None:
            raise ConflictError("user is already a member")
        if not chat.is_public:
            pending = await self._invites.get_pending(chat_id, target_id)
            if pending is not None:
                raise ConflictError("user already has a pending invite")
            invite = Invite(
                id=0,
                chat_id=chat_id,
                inviter_id=actor_id,
                invitee_id=target_id,
                token=None,
                status=InviteStatus.PENDING,
                expires_at=None,
                created_at=utcnow(),
            )
            created = await self._invites.add(invite)
            return {"invite": created}
        member = await self._members.add(
            ChatMember(
                id=0,
                chat_id=chat_id,
                user_id=target_id,
                role=MemberRole.MEMBER,
                joined_at=utcnow(),
                invited_by_id=actor_id,
            )
        )
        return {"member": (member, target)}

    async def remove_member(self, actor_id: int, chat_id: int, target_id: int) -> None:
        chat = await self._get_chat(chat_id)
        if chat.type is not ChatType.GROUP:
            raise ValidationError("cannot remove members from a private chat")
        actor = await self._require_member(chat_id, actor_id)
        target_member = await self._members.get_pair(chat_id, target_id)
        if target_member is None:
            raise NotFoundError("user is not a member of this chat")
        if not can_remove_member(actor.role, target_member.role):
            raise ForbiddenError("you cannot remove this member")
        await self._members.remove(chat_id, target_id)

    async def join_group(self, actor_id: int, chat_id: int) -> None:
        chat = await self._get_chat(chat_id)
        if chat.type is not ChatType.GROUP or not chat.is_public:
            raise ForbiddenError("this group is not public")
        if await self._members.get_pair(chat_id, actor_id) is not None:
            raise ConflictError("you are already a member")
        await self._members.add(
            ChatMember(
                id=0,
                chat_id=chat_id,
                user_id=actor_id,
                role=MemberRole.MEMBER,
                joined_at=utcnow(),
            )
        )

    async def leave_chat(self, actor_id: int, chat_id: int) -> None:
        chat = await self._get_chat(chat_id)
        if chat.type is not ChatType.GROUP:
            raise ValidationError("cannot leave a private chat")
        actor = await self._require_member(chat_id, actor_id)
        remaining = [m for m in await self._members.list_by_chat(chat_id) if m.user_id != actor_id]
        if not remaining:
            await self._chats.delete_with_contents(chat_id)
            return
        if actor.role is MemberRole.OWNER:
            new_owner = next(
                (m for m in remaining if m.role is MemberRole.ADMIN),
                remaining[0],
            )
            new_owner.role = MemberRole.OWNER
            await self._members.update(new_owner)
            chat.owner_id = new_owner.user_id
            await self._chats.update(chat)
        await self._members.remove(chat_id, actor_id)

    async def promote_to_admin(self, actor_id: int, chat_id: int, target_id: int) -> None:
        chat = await self._get_chat(chat_id)
        if chat.type is not ChatType.GROUP:
            raise ValidationError("cannot promote in a private chat")
        actor = await self._require_member(chat_id, actor_id)
        if not can_promote(actor.role):
            raise ForbiddenError("only the owner can promote admins")
        target_member = await self._members.get_pair(chat_id, target_id)
        if target_member is None:
            raise NotFoundError("user is not a member of this chat")
        if target_member.role is MemberRole.OWNER:
            raise ValidationError("owner is already the highest role")
        if target_member.role is MemberRole.ADMIN:
            raise ConflictError("user is already an admin")
        target_member.role = MemberRole.ADMIN
        await self._members.update(target_member)
