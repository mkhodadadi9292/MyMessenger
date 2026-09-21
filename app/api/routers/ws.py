import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.realtime import broadcast_new_message
from app.config import Settings
from app.domain.exceptions import DomainError, UnauthorizedError
from app.infrastructure.auth.jwt import TOKEN_ACCESS, decode_token
from app.infrastructure.realtime import ConnectionManager
from app.infrastructure.repositories.chat import SqlChatMemberRepository, SqlChatRepository
from app.infrastructure.repositories.contact import SqlBlockRepository
from app.infrastructure.repositories.message import SqlArtifactRepository, SqlMessageRepository
from app.infrastructure.repositories.user import SqlUserRepository
from app.application.message_service import MessageService

logger = logging.getLogger("app.realtime")

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    settings: Settings = websocket.app.state.settings
    try:
        if not token:
            raise UnauthorizedError("missing token")
        payload = decode_token(token, settings)
        if payload.get("type") != TOKEN_ACCESS:
            raise UnauthorizedError("invalid token")
        user_id = int(payload["sub"])
    except (UnauthorizedError, ValueError, KeyError):
        await websocket.close(code=4401)
        return

    hub: ConnectionManager = websocket.app.state.realtime
    await websocket.accept()
    await hub.connect(user_id, websocket)
    try:
        while True:
            raw = await websocket.receive_json()
            msg_type = raw.get("type")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg_type == "subscribe":
                await hub.subscribe(user_id, int(raw["chat_id"]))
            elif msg_type == "unsubscribe":
                await hub.unsubscribe(user_id, int(raw["chat_id"]))
            elif msg_type == "message.send":
                await _handle_send(websocket, hub, settings, user_id, raw)
            else:
                await websocket.send_json({"type": "error", "detail": "unknown message type"})
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("websocket handler error")
    finally:
        await hub.disconnect(user_id, websocket)


async def _handle_send(
    websocket: WebSocket, hub: ConnectionManager, settings: Settings, user_id: int, raw: dict
) -> None:
    chat_id = int(raw.get("chat_id", 0))
    text = raw.get("text")
    reply_to_id = raw.get("reply_to_id")
    session_factory = websocket.app.state.session_factory
    async with session_factory() as session:
        try:
            service = MessageService(
                SqlMessageRepository(session),
                SqlArtifactRepository(session),
                SqlChatRepository(session),
                SqlChatMemberRepository(session),
                SqlUserRepository(session),
                SqlBlockRepository(session),
            )
            message = await service.send_message(user_id, chat_id, text, reply_to_id)
            sender = await SqlUserRepository(session).get(user_id)
            event = await broadcast_new_message(
                hub,
                SqlChatMemberRepository(session),
                service,
                message,
                sender,
                chat_id,
            )
            await session.commit()
            await websocket.send_json(
                {"type": "message.sent", "message": event}
            )
        except DomainError as exc:
            await session.rollback()
            await websocket.send_json({"type": "error", "detail": str(exc)})
        except Exception:
            await session.rollback()
            raise
