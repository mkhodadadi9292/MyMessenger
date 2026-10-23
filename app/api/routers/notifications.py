import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import get_current_user, get_notification_service
from app.application.notification_service import NotificationService
from app.config import Settings
from app.domain.entities import User
from app.domain.exceptions import UnauthorizedError
from app.infrastructure.auth.jwt import TOKEN_ACCESS, decode_token
from app.infrastructure.repositories.user import SqlUserRepository
from app.infrastructure.sse import SseHub

logger = logging.getLogger("app.sse")

router = APIRouter(tags=["notifications"])


class MarkReadIn(BaseModel):
    chat_id: int | None = None


@router.get("/notifications")
async def list_notifications(
    before_id: int | None = None,
    limit: int | None = None,
    current_user: User = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> list[dict]:
    return await service.list_for_user(current_user.id, before_id, limit)


@router.get("/notifications/unread-count")
async def unread_count(
    current_user: User = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> dict:
    return {"count": await service.unread_count(current_user.id)}


@router.post("/notifications/read")
async def mark_read(
    body: MarkReadIn,
    current_user: User = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> dict:
    unread = await service.mark_read(current_user.id, body.chat_id)
    return {"ok": True, "unread_count": unread}


async def _stream_user_id(request: Request) -> int:
    """EventSource cannot send headers → token comes from the query string
    (like /ws); the Authorization header is also accepted for curl/tests."""
    settings: Settings = request.app.state.settings
    token = request.query_params.get("token")
    if not token:
        authorization = request.headers.get("Authorization", "")
        scheme, _, header_token = authorization.partition(" ")
        if scheme.lower() == "bearer":
            token = header_token
    if not token:
        raise UnauthorizedError("missing token")
    try:
        payload = decode_token(token, settings)
        if payload.get("type") != TOKEN_ACCESS:
            raise UnauthorizedError("invalid access token")
        return int(payload["sub"])
    except (ValueError, KeyError):
        raise UnauthorizedError("invalid access token") from None


@router.get("/notifications/stream")
async def notification_stream(request: Request) -> StreamingResponse:
    user_id = await _stream_user_id(request)
    session_factory = request.app.state.session_factory
    hub: SseHub = request.app.state.sse

    async with session_factory() as session:
        if await SqlUserRepository(session).get(user_id) is None:
            raise UnauthorizedError("user not found")

    queue = hub.subscribe(user_id)

    async def event_stream():
        try:
            yield "retry: 3000\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(
                        queue.get(), timeout=request.app.state.settings.sse_keepalive_seconds
                    )
                    yield f"event: {event['type']}\ndata: {json.dumps(event, default=str)}\n\n"
                except TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            hub.unsubscribe(user_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
