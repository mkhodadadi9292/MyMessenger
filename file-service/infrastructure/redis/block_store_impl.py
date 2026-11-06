from core.interfaces.block_store import IBlockStore


class RedisBlockStoreImpl(IBlockStore):
    def __init__(self, redis, scope: str, ttl_seconds: int = 3600):
        self.redis = redis
        self.scope = scope
        self.ttl = ttl_seconds

    def _key(self, lookup_key: str, req_id: str) -> str:
        return f"file:{self.scope}:{lookup_key}:{req_id}"

    async def is_blocked(self, lookup_key: str, req_id: str) -> bool:
        return await self.redis.exists(self._key(lookup_key, req_id)) == 1

    async def block(self, lookup_key: str, req_id: str) -> None:
        await self.redis.set(self._key(lookup_key, req_id), 1, ex=self.ttl)