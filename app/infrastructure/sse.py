import asyncio
import logging

logger = logging.getLogger("app.sse")


class SseHub:
    """In-process fan-out for SSE streams: one asyncio.Queue per open stream."""

    def __init__(self) -> None:
        self._subscribers: dict[int, set[asyncio.Queue]] = {}

    def subscribe(self, user_id: int) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(user_id, set()).add(queue)
        return queue

    def unsubscribe(self, user_id: int, queue: asyncio.Queue) -> None:
        queues = self._subscribers.get(user_id)
        if queues:
            queues.discard(queue)
            if not queues:
                self._subscribers.pop(user_id, None)

    async def publish(self, user_id: int, event: dict) -> None:
        for queue in list(self._subscribers.get(user_id, ())):
            try:
                queue.put_nowait(event)
            except Exception:
                logger.warning("failed to enqueue SSE event for user %s", user_id, exc_info=True)
                self.unsubscribe(user_id, queue)

    async def publish_many(self, user_ids: set[int], event: dict) -> None:
        for user_id in user_ids:
            await self.publish(user_id, event)
