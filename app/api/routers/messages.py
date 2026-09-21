from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user, get_message_service
from app.api.schemas.common import message_to_out, user_to_public
from app.application.message_service import MessageService
from app.domain.entities import User

router = APIRouter(tags=["messages"])


class MessageCreateIn(BaseModel):
    text: str | None = None
    reply_to_id: int | None = None


class MessageUpdateIn(BaseModel):
    text: str


@router.get("/chats/{chat_id}/messages")
async def list_messages(
    chat_id: int,
    before_id: int | None = None,
    limit: int | None = None,
    current_user: User = Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
) -> list[dict]:
    entries = await service.list_messages(current_user.id, chat_id, before_id, limit)
    return [
        message_to_out(message, sender, artifact).model_dump()
        for message, sender, artifact in entries
    ]


@router.post("/chats/{chat_id}/messages")
async def send_message(
    chat_id: int,
    body: MessageCreateIn,
    current_user: User = Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
) -> dict:
    message = await service.send_message(current_user.id, chat_id, body.text, body.reply_to_id)
    return message_to_out(message, current_user, None).model_dump()


@router.patch("/messages/{message_id}")
async def edit_message(
    message_id: int,
    body: MessageUpdateIn,
    current_user: User = Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
) -> dict:
    message = await service.edit_message(current_user.id, message_id, body.text)
    return message_to_out(message, current_user, None).model_dump()


@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: int,
    current_user: User = Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
) -> dict:
    await service.delete_message(current_user.id, message_id)
    return {"ok": True}
