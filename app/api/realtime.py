from app.api.schemas.common import message_to_out, reply_preview_to_out
from app.application.message_service import MessageService
from app.domain.entities import Artifact, Message, User
from app.domain.repositories.chat import ChatMemberRepository
from app.infrastructure.realtime import ConnectionManager


async def build_message_event(
    message_service: MessageService,
    message: Message,
    sender: User | None,
    artifact: Artifact | None = None,
) -> dict:
    previews = await message_service.build_reply_previews([message])
    preview = None
    if message.reply_to_id is not None and message.reply_to_id in previews:
        target, target_sender, target_artifact = previews[message.reply_to_id]
        preview = reply_preview_to_out(target, target_sender, target_artifact)
    return message_to_out(message, sender, artifact, preview).model_dump(mode="json")


async def broadcast_new_message(
    hub: ConnectionManager,
    members: ChatMemberRepository,
    message_service: MessageService,
    message: Message,
    sender: User | None,
    chat_id: int,
    artifact: Artifact | None = None,
) -> dict:
    event = await build_message_event(message_service, message, sender, artifact)
    await hub.broadcast_to_chat(chat_id, {"type": "message.new", "message": event})
    member_ids = {m.user_id for m in await members.list_by_chat(chat_id)}
    for user_id in member_ids:
        await hub.send_to_user(user_id, {"type": "chat.list_changed"})
    return event


async def notify_chat_list_changed(hub: ConnectionManager, user_ids: set[int]) -> None:
    for user_id in user_ids:
        await hub.send_to_user(user_id, {"type": "chat.list_changed"})
