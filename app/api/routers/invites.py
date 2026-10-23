from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_invite_service
from app.api.notify import notify_new_invite
from app.application.invite_service import InviteService
from app.domain.entities import User

router = APIRouter(tags=["invites"])


class InviteUserIn(BaseModel):
    user_id: int


class InviteLinkIn(BaseModel):
    ttl_seconds: int | None = None


@router.post("/chats/{chat_id}/invites")
async def invite_user(
    chat_id: int,
    body: InviteUserIn,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: InviteService = Depends(get_invite_service),
    db: AsyncSession = Depends(get_db),
) -> dict:
    invite = await service.invite_user(current_user.id, chat_id, body.user_id)
    await db.commit()
    await notify_new_invite(request.app.state.sse, db, invite)
    return {"invite_id": invite.id, "status": invite.status.value}


@router.post("/chats/{chat_id}/invite-links")
async def create_invite_link(
    chat_id: int,
    body: InviteLinkIn | None = None,
    current_user: User = Depends(get_current_user),
    service: InviteService = Depends(get_invite_service),
    db: AsyncSession = Depends(get_db),
) -> dict:
    ttl = body.ttl_seconds if body else None
    result = await service.create_invite_link(current_user.id, chat_id, ttl)
    await db.commit()
    return result


@router.get("/invites/{token}")
async def get_invite_info(
    token: str,
    current_user: User = Depends(get_current_user),
    service: InviteService = Depends(get_invite_service),
) -> dict:
    return await service.get_invite_info(token)


@router.post("/invites/{token}/accept")
async def accept_invite_link(
    token: str,
    current_user: User = Depends(get_current_user),
    service: InviteService = Depends(get_invite_service),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await service.accept_link(current_user.id, token)
    await db.commit()
    return {"ok": True}


@router.get("/me/invites")
async def list_my_invites(
    current_user: User = Depends(get_current_user),
    service: InviteService = Depends(get_invite_service),
) -> list[dict]:
    return await service.list_my_invites(current_user.id)


@router.post("/me/invites/{invite_id}/accept")
async def accept_invite(
    invite_id: int,
    current_user: User = Depends(get_current_user),
    service: InviteService = Depends(get_invite_service),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await service.accept_invite(current_user.id, invite_id)
    await db.commit()
    return {"ok": True}


@router.post("/me/invites/{invite_id}/decline")
async def decline_invite(
    invite_id: int,
    current_user: User = Depends(get_current_user),
    service: InviteService = Depends(get_invite_service),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await service.decline_invite(current_user.id, invite_id)
    await db.commit()
    return {"ok": True}
