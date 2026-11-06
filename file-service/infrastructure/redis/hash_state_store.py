from typing import Optional
from redis.asyncio import Redis

from core.interfaces.hash_store import IHashStateStore


class RedisHashStateStore(IHashStateStore):
    def __init__(self, redis: Redis, ttl_seconds: int = 660):
        self.redis = redis
        self.ttl = ttl_seconds

    @staticmethod
    def _key(session_id: str) -> str:
        return f"file:upload:hash_state:{session_id}"

    async def set_state(self, session_id: str, state: str) -> None:
        key = self._key(session_id)
        await self.redis.set(key, state, ex=self.ttl)

    async def get_state(self, session_id: str) -> Optional[str]:
        key = self._key(session_id)
        state = await self.redis.get(key)

        if state is None:
            return None

        await self.redis.expire(key, self.ttl)

        if isinstance(state, bytes):
            return state.decode("utf-8")

        return state

    async def delete_state(self, session_id: str) -> None:
        key = self._key(session_id)
        await self.redis.delete(key)