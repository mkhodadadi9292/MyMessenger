from redis.asyncio import Redis

from core.use_cases.delete_file_by_session_uc import DeleteFileBySessionUseCase


class SessionExpireListener:
    def __init__(
        self,
        redis: Redis,
        delete_uc: DeleteFileBySessionUseCase,
    ):
        self.redis = redis
        self.delete_uc = delete_uc

    async def start(self):
        pubsub = self.redis.pubsub()
        await pubsub.psubscribe("__keyevent@1__:expired")

        async for message in pubsub.listen():
            if message["type"] != "pmessage":
                continue

            key = message["data"]
            if not isinstance(key, str):
                key = key.decode()

            if key.startswith("file:upload:session:"):
                session_id = key.split(":")[-1]

                await self.delete_uc.execute(session_id)
