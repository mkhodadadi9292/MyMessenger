import uuid
from typing import Any, Awaitable, Callable
import redis.asyncio as redis
from infrastructure.redis.redis_client import RedisClient
from infrastructure.logging.logger import logger


class RedisStreamWorker:
    def __init__(
        self,
        stream_key: str,
        group: str,
        consumer_prefix: str,
        handler: Callable[[dict], Awaitable[None]],
    ):
        self.stream_key = stream_key
        self.group = group
        self.handler = handler
        self.redis_client = RedisClient()
        self.consumer_name = f"{consumer_prefix}_{uuid.uuid4()}"

    async def ensure_group(self, redis_client: redis.Redis):
        try:
            await redis_client.xgroup_create(self.stream_key, self.group, id="0", mkstream=True)
            logger.info(f"Redis group '{self.group}' created.")
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.info(f"Redis group '{self.group}' already exists.")
            else:
                logger.error(f"Error creating Redis group: {e}")
                raise

    async def run(self):
        redis_client: Any = await self.redis_client.get_client()
        await self.ensure_group(redis_client)
        logger.info(f"Worker started: {self.consumer_name}")

        while True:
            try:
                messages = await redis_client.xreadgroup(
                    groupname=self.group,
                    consumername=self.consumer_name,
                    streams={self.stream_key: ">"},
                    count=10,
                    block=0,
                )
            except redis.ResponseError as e:
                logger.error(f"xreadgroup response error: {e}")
                continue
            except redis.RedisError as e:
                logger.error(f"xreadgroup redis error: {e}")
                continue
            except Exception as e:
                logger.error(f"xreadgroup unexpected error: {e}")
                continue

            if not messages:
                continue

            for _, entries in messages:
                for msg_id, fields in entries:
                    try:
                        await self.handler(fields)
                    except Exception as e:
                        logger.error(f"handler error for {self.stream_key}: {e}")
                    finally:
                        await redis_client.xack(self.stream_key, self.group, msg_id)