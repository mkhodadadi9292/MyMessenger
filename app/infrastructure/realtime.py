import logging

from fastapi import WebSocket

logger = logging.getLogger("app.realtime")


class ConnectionManager:
    """Tracks user websockets and chat subscriptions for fan-out."""

    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = {}
        self._subscriptions: dict[int, set[int]] = {}  # chat_id -> user_ids

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        self._connections.setdefault(user_id, set()).add(websocket)

    async def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        sockets = self._connections.get(user_id)
        if sockets:
            sockets.discard(websocket)
            if not sockets:
                self._connections.pop(user_id, None)
        # remove the user from every chat subscription
        for chat_users in self._subscriptions.values():
            chat_users.discard(user_id)

    async def subscribe(self, user_id: int, chat_id: int) -> None:
        self._subscriptions.setdefault(chat_id, set()).add(user_id)

    async def unsubscribe(self, user_id: int, chat_id: int) -> None:
        users = self._subscriptions.get(chat_id)
        if users:
            users.discard(user_id)
            if not users:
                self._subscriptions.pop(chat_id, None)

    async def send_to_user(self, user_id: int, payload: dict) -> None:
        for websocket in list(self._connections.get(user_id, ())):
            try:
                await websocket.send_json(payload)
            except Exception:
                logger.debug("failed to send ws event to user %s", user_id, exc_info=True)

    async def broadcast_to_chat(self, chat_id: int, payload: dict) -> None:
        for user_id in list(self._subscriptions.get(chat_id, ())):
            await self.send_to_user(user_id, payload)
