import json
from typing import List, Optional
from redis.asyncio import Redis

from core.entities.file_metadata import FileMetadata
from core.interfaces.metadata_store import IMetadataStore
from infrastructure.logging.logger import logger


class RedisMetadataStore(IMetadataStore):
    def __init__(self, redis: Redis, ttl_seconds: int = 604800):
        self.redis = redis
        self.ttl = ttl_seconds

    @staticmethod
    def _key(lookup_key: str) -> str:
        return f"file:metadata:{lookup_key}"

    async def get_batch(self, lookup_keys: List[str]) -> List[Optional[FileMetadata]]:
        keys = [self._key(k) for k in lookup_keys]

        try:
            raw_results = await self.redis.mget(keys)

            results: List[Optional[FileMetadata]] = []

            for idx, raw in enumerate(raw_results):
                if raw is None:
                    results.append(None)
                    continue

                try:
                    data = json.loads(raw)

                    meta = FileMetadata(
                        id=data["id"],
                        lookup_key=data["lookup_key"],
                        name=data["name"],
                        size_bytes=data["size_bytes"],
                        has_thumbnail=data["has_thumbnail"],
                        is_private=data["is_private"],
                        file_kind=data["file_kind"],
                    )

                    results.append(meta)

                    await self.redis.expire(keys[idx], self.ttl)

                except Exception as e:
                    logger.error(
                        "Redis metadata decode failed",
                        extra={
                            "lookup_key": lookup_keys[idx],
                            "error": str(e),
                        },
                    )
                    results.append(None)

            return results

        except Exception as e:
            logger.error(
                "Redis metadata batch read failed",
                extra={
                    "lookup_keys": lookup_keys,
                    "error": str(e),
                },
            )
            return [None] * len(lookup_keys)

    async def set(self, metadata: FileMetadata) -> None:
        key = self._key(metadata.lookup_key)

        try:
            payload = json.dumps(
                {
                    "id": metadata.id,
                    "lookup_key": metadata.lookup_key,
                    "name": metadata.name,
                    "size_bytes": metadata.size_bytes,
                    "has_thumbnail": metadata.has_thumbnail,
                    "is_private": metadata.is_private,
                    "file_kind": metadata.file_kind,
                }
            )

            await self.redis.set(key, payload, ex=self.ttl)

        except Exception as e:
            logger.error(
                "Redis metadata cache write failed",
                extra={
                    "lookup_key": metadata.lookup_key,
                    "error": str(e),
                },
            )