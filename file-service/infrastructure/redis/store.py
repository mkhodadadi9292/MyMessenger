import json
from typing import Optional
from redis.asyncio import Redis

from core.interfaces.store import IStore
from core.entities.upload_session import UploadSession


class RedisStore(IStore):
    def __init__(self, redis: Redis, ttl_seconds: int = 600):
        self.redis = redis
        self.ttl = ttl_seconds

    @staticmethod
    def _key(session_id: str) -> str:
        return f"file:upload:session:{session_id}"

    async def init_session(self, session_id: str, public_id: str):
        session = UploadSession(
            session_id=session_id,
            public_id=public_id,
            last_chunk_number=0,
        )
        key = self._key(session_id)
        await self.redis.set(key, json.dumps(session.__dict__), ex=21600)

    async def update_session(
        self,
        session_id: str,
        public_id: str,
        last_chunk_number: int,
        hash_in_last: bool,
        file_type: Optional[str],
        total_chunks: Optional[int],
    ):
        key = self._key(session_id)
        raw = await self.redis.get(key)
        if raw is None:
            return

        data = json.loads(raw)

        data["public_id"] = public_id
        data["last_chunk_number"] = last_chunk_number
        data["hash_in_last"] = hash_in_last
        data["file_type"] = file_type
        data["total_chunks"] = total_chunks

        await self.redis.set(key, json.dumps(data), ex=self.ttl)

    async def load(self, session_id: str) -> Optional[UploadSession]:
        key = self._key(session_id)
        raw = await self.redis.get(key)
        if raw is None:
            return None

        await self.redis.expire(key, self.ttl)
        data = json.loads(raw)
        return UploadSession(**data)

    async def delete(self, session_id: str):
        key = self._key(session_id)
        await self.redis.delete(key)
