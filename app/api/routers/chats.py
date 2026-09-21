from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_chat_service, get_current_user
from app.api.schemas.common import chat_to_out, member_to_out, message_to_out, user_to_public
from app.application.chat_service import ChatService
from app.domain.entities import User

router = APIRouter(prefix="/chats", tags=["chats"])


class PrivateChatIn(BaseModel):
    user_id: int


class GroupCreateIn(BaseModel):
    title: str
    description: str | None = None
    is_public: bool


class ChatUpdateIn(BaseModel):
    title: str | None = None
    description: str | None = None


class MemberAddIn(BaseModel):
    user_id: int


@router.get("")
async def list_chats(
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> list[dict]:
    items = await service.list_chats(current_user.id)
    peers = await service.peers_for_private_chats(current_user.id, [c for c, *_ in items])
    result = []
    for chat, last_message, sender, artifact in items:
        item = chat_to_out(chat).model_dump()
        peer = peers.get(chat.id)
        item["peer"] = user_to_public(peer).model_dump() if peer else None
        item["last_message"] = (
            message_to_out(last_message, sender, artifact).model_dump() if last_message else None
        )
        result.append(item)
    return result


@router.post("/private")
async def open_private_chat(
    body: PrivateChatIn,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    chat = await service.open_private_chat(current_user.id, body.user_id)
    return chat_to_out(chat).model_dump()


@router.post("/groups")
async def create_group(
    body: GroupCreateIn,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    chat = await service.create_group(current_user.id, body.title, body.description, body.is_public)
    return chat_to_out(chat).model_dump()


@router.get("/{chat_id}")
async def get_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    chat = await service.get_chat(current_user.id, chat_id)
    return chat_to_out(chat).model_dump()


@router.patch("/{chat_id}")
async def update_chat(
    chat_id: int,
    body: ChatUpdateIn,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    chat = await service.update_chat(current_user.id, chat_id, body.title, body.description)
    return chat_to_out(chat).model_dump()


@router.get("/{chat_id}/members")
async def list_members(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> list[dict]:
    entries = await service.list_members(current_user.id, chat_id)
    return [member_to_out(member, user).model_dump() for member, user in entries]


@router.post("/{chat_id}/members")
async def add_member(
    chat_id: int,
    body: MemberAddIn,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    result = await service.add_member(current_user.id, chat_id, body.user_id)
    if "invite" in result:
        invite = result["invite"]
        return {"invite_id": invite.id, "status": invite.status.value}
    member, user = result["member"]
    return member_to_out(member, user).model_dump()


@router.delete("/{chat_id}/members/{user_id}")
async def remove_member(
    chat_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    await service.remove_member(current_user.id, chat_id, user_id)
    return {"ok": True}


@router.post("/{chat_id}/join")
async def join_group(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    await service.join_group(current_user.id, chat_id)
    return {"ok": True}


@router.delete("/{chat_id}/leave")
async def leave_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    await service.leave_chat(current_user.id, chat_id)
    return {"ok": True}


@router.post("/{chat_id}/admins/{user_id}")
async def promote_to_admin(
    chat_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    await service.promote_to_admin(current_user.id, chat_id, user_id)
    return {"ok": True}
