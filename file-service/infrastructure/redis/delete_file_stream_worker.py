from infrastructure.redis.stream_worker import RedisStreamWorker
from infrastructure.di.providers import get_delete_file_by_lookupkey_uc
from infrastructure.data.database import SessionLocal
from infrastructure.logging.logger import logger

STREAM_KEY = "file.delete.requests"
GROUP = "file_delete_group"


async def handle_delete_event(fields: dict) -> None:
    lookup_key = fields.get("lookup_key")
    req_id = fields.get("req_id")

    if not lookup_key or not req_id:
        logger.warning(f"Invalid message format: {fields}")
        return

    async with SessionLocal() as session:
        uc = await get_delete_file_by_lookupkey_uc(session)
        result = await uc.execute(lookup_key, req_id)
        logger.info(
            f"Processed delete request: lookup_key={lookup_key}, req_id={req_id}, result={result['status']}"
        )


def build_delete_file_stream_worker() -> RedisStreamWorker:
    return RedisStreamWorker(
        stream_key=STREAM_KEY,
        group=GROUP,
        consumer_prefix="file_delete_worker",
        handler=handle_delete_event,
    )