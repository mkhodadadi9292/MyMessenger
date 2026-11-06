from core.interfaces.download_access_store import IDownloadAccessStore


class RedisDownloadAccessStore(IDownloadAccessStore):
    def __init__(self, client, ttl_seconds: int = 600):
        self.client = client
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def _key(public_id: str, lookup_key: str) -> str:
        return f"download_access:{public_id}:{lookup_key}"

    async def is_allowed(self, public_id: str, lookup_key: str) -> bool:
        return await self.client.exists(self._key(public_id, lookup_key)) == 1

    async def allow(self, public_id: str, lookup_key: str) -> None:
        await self.client.set(self._key(public_id, lookup_key), "1", ex=self.ttl_seconds)