from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user, get_message_service
from app.api.schemas.common import message_to_out, reply_preview_to_out
from app.application.message_service import MessageService
from app.domain.entities import Artifact, Message, User

router = APIRouter(tags=["messages"])


class MessageCreateIn(BaseModel):
    text: str | None = None
    reply_to_id: int | None = None


class MessageUpdateIn(BaseModel):
    text: str


async def _message_dicts(
    service: MessageService, entries: list[tuple[Message, User | None, Artifact | None]]
) -> list[dict]:
    messages = [message for message, _, _ in entries]
    previews = await service.build_reply_previews(messages)
    result = []
    for message, sender, artifact in entries:
        preview = None
        if message.reply_to_id is not None and message.reply_to_id in previews:
            target, target_sender, target_artifact = previews[message.reply_to_id]
            preview = reply_preview_to_out(target, target_sender, target_artifact)
        result.append(message_to_out(message, sender, artifact, preview).model_dump())
    return result


@router.get("/chats/{chat_id}/messages")
async def list_messages(
    chat_id: int,
    before_id: int | None = None,
    limit: int | None = None,
    current_user: User = Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
) -> list[dict]:
    entries = await service.list_messages(current_user.id, chat_id, before_id, limit)
    return await _message_dicts(service, entries)


@router.post("/chats/{chat_id}/messages")
async def send_message(
    chat_id: int,
    body: MessageCreateIn,
    current_user: User = Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
) -> dict:
    message = await service.send_message(current_user.id, chat_id, body.text, body.reply_to_id)
    return (await _message_dicts(service, [(message, current_user, None)]))[0]


@router.patch("/messages/{message_id}")
async def edit_message(
    message_id: int,
    body: MessageUpdateIn,
    current_user: User = Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
) -> dict:
    message = await service.edit_message(current_user.id, message_id, body.text)
    return (await _message_dicts(service, [(message, current_user, None)]))[0]


@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: int,
    current_user: User = Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
) -> dict:
    await service.delete_message(current_user.id, message_id)
    return {"ok": True}
