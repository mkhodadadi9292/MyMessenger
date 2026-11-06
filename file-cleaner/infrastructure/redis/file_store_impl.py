from core.interfaces.file_store import IFileStore
from infrastructure.redis.redis_client import RedisClient

class FileStore(IFileStore):
    def __init__(self, redis_client: RedisClient):
        self.redis_client = redis_client

    @staticmethod
    def _key(session_id: str) -> str:
        return f"file:upload:session:{session_id}"

    async def exists(self, session_id: str) -> bool:
        client = await self.redis_client.get_client()
        key = self._key(session_id)
        raw = await client.get(key)
        return raw is not None