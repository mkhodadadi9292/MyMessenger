import asyncio
import redis.asyncio as redis
from settings import settings


class RedisClient:
    def __init__(self):
        self.url = settings.redis_url
        self.client: redis.Redis | None = None

    async def get_client(self) -> redis.Redis:
        if self.client is not None:
            return self.client

        backoff = 1
        max_backoff = 30

        while True:
            try:
                client = redis.from_url(self.url, decode_responses=True)
                await client.ping()
                self.client = client
                return client

            except Exception as e:
                print(f"[Redis] Connection failed: {e}. Retrying in {backoff} seconds...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

    async def publish(self, channel: str, message: str):
        client = await self.get_client()
        await client.publish(channel, message)
