import secrets
from datetime import timedelta

from app.domain.entities import Chat, ChatMember, Invite, User
from app.domain.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.domain.permissions import can_invite
from app.domain.repositories.chat import ChatMemberRepository, ChatRepository, InviteRepository
from app.domain.repositories.user import UserRepository
from app.domain.time import utcnow
from app.domain.value_objects import ChatType, InviteStatus, MemberRole

DEFAULT_LINK_TTL_SECONDS = 86400


class InviteService:
    def __init__(
        self,
        invites: InviteRepository,
        chats: ChatRepository,
        members: ChatMemberRepository,
        users: UserRepository,
    ) -> None:
        self._invites = invites
        self._chats = chats
        self._members = members
        self._users = users

    async def _get_private_group(self, chat_id: int) -> Chat:
        chat = await self._chats.get(chat_id)
        if chat is None:
            raise NotFoundError("chat not found")
        if chat.type is not ChatType.GROUP or chat.is_public:
            raise ValidationError("invites are only for private groups")
        return chat

    async def _require_admin(self, chat_id: int, actor_id: int) -> ChatMember:
        member = await self._members.get_pair(chat_id, actor_id)
        if member is None:
            raise ForbiddenError("you are not a member of this chat")
        if not can_invite(member.role):
            raise ForbiddenError("only admins can invite")
        return member

    async def invite_user(self, actor_id: int, chat_id: int, target_id: int) -> Invite:
        await self._get_private_group(chat_id)
        await self._require_admin(chat_id, actor_id)
        target = await self._users.get(target_id)
        if target is None:
            raise NotFoundError("user not found")
        if await self._members.get_pair(chat_id, target_id) is not None:
            raise ConflictError("user is already a member")
        if await self._invites.get_pending(chat_id, target_id) is not None:
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
        return await self._invites.add(invite)

    async def create_invite_link(
        self, actor_id: int, chat_id: int, ttl_seconds: int | None
    ) -> dict:
        await self._get_private_group(chat_id)
        await self._require_admin(chat_id, actor_id)
        ttl = ttl_seconds if ttl_seconds is not None else DEFAULT_LINK_TTL_SECONDS
        invite = Invite(
            id=0,
            chat_id=chat_id,
            inviter_id=actor_id,
            invitee_id=None,
            token=secrets.token_urlsafe(24),
            status=InviteStatus.PENDING,
            expires_at=utcnow() + timedelta(seconds=ttl),
            created_at=utcnow(),
        )
        created = await self._invites.add(invite)
        return {
            "token": created.token,
            "url": f"/api/v1/invites/{created.token}",
            "expires_at": created.expires_at,
        }

    async def get_invite_info(self, token: str) -> dict:
        invite = await self._invites.get_by_token(token)
        if invite is None:
            raise NotFoundError("invite link not found")
        invite.expire_if_needed(utcnow())
        if invite.status is InviteStatus.EXPIRED:
            await self._invites.update(invite)
            raise ValidationError("invite link has expired")
        chat = await self._chats.get(invite.chat_id)
        inviter = await self._users.get(invite.inviter_id)
        return {
            "chat_id": chat.id,
            "title": chat.title,
            "inviter_name": str(inviter.username) if inviter else None,
            "expires_at": invite.expires_at,
        }

    async def accept_link(self, actor_id: int, token: str) -> None:
        invite = await self._invites.get_by_token(token)
        if invite is None:
            raise NotFoundError("invite link not found")
        invite.expire_if_needed(utcnow())
        if invite.status is InviteStatus.EXPIRED:
            await self._invites.update(invite)
            raise ValidationError("invite link has expired")
        if await self._members.get_pair(invite.chat_id, actor_id) is not None:
            raise ConflictError("you are already a member")
        if invite.status is not InviteStatus.PENDING:
            raise ValidationError("invite is not pending")
        await self._members.add(
            ChatMember(
                id=0,
                chat_id=invite.chat_id,
                user_id=actor_id,
                role=MemberRole.MEMBER,
                joined_at=utcnow(),
                invited_by_id=invite.inviter_id,
            )
        )
        invite.accept()
        await self._invites.update(invite)

    async def list_my_invites(self, user_id: int) -> list[dict]:
        invites = await self._invites.list_pending_for_invitee(user_id)
        if not invites:
            return []
        chat_ids = [i.chat_id for i in invites]
        inviter_ids = [i.inviter_id for i in invites]
        chats = await self._chats.list_by_ids(chat_ids)
        inviters = await self._users.list_by_ids(inviter_ids)
        chat_by_id = {c.id: c for c in chats}
        inviter_by_id = {u.id: u for u in inviters}
        result = []
        for invite in invites:
            chat = chat_by_id.get(invite.chat_id)
            inviter = inviter_by_id.get(invite.inviter_id)
            result.append(
                {
                    "invite_id": invite.id,
                    "chat_id": invite.chat_id,
                    "title": chat.title if chat else None,
                    "inviter_name": str(inviter.username) if inviter else None,
                    "created_at": invite.created_at,
                }
            )
        return result

    async def _respond(self, user_id: int, invite_id: int, accept: bool) -> None:
        invite = await self._invites.get(invite_id)
        if invite is None:
            raise NotFoundError("invite not found")
        if invite.invitee_id != user_id:
            raise ForbiddenError("this invite is not for you")
        invite.expire_if_needed(utcnow())
        if invite.status is InviteStatus.EXPIRED:
            await self._invites.update(invite)
            raise ValidationError("invite has expired")
        if invite.status is not InviteStatus.PENDING:
            raise ValidationError("invite is not pending")
        if accept:
            await self._members.add(
                ChatMember(
                    id=0,
                    chat_id=invite.chat_id,
                    user_id=user_id,
                    role=MemberRole.MEMBER,
                    joined_at=utcnow(),
                    invited_by_id=invite.inviter_id,
                )
            )
            invite.accept()
        else:
            invite.decline()
        await self._invites.update(invite)

    async def accept_invite(self, user_id: int, invite_id: int) -> None:
        await self._respond(user_id, invite_id, accept=True)

    async def decline_invite(self, user_id: int, invite_id: int) -> None:
        await self._respond(user_id, invite_id, accept=False)
