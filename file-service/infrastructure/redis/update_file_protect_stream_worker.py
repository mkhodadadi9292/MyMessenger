from infrastructure.redis.stream_worker import RedisStreamWorker
from infrastructure.di.providers import get_update_file_protect_uc
from infrastructure.data.database import SessionLocal
from infrastructure.logging.logger import logger

STREAM_KEY = "file.protect.requests"
GROUP = "file_protect_group"


async def handle_protect_event(fields: dict) -> None:
    lookup_key = fields.get("lookup_key")
    req_id = fields.get("req_id")
    is_protect_raw = fields.get("is_protect")

    if not lookup_key or not req_id or is_protect_raw is None:
        logger.warning(f"Invalid message format: {fields}")
        return

    is_protect = is_protect_raw.lower() in ("true", "1")

    async with SessionLocal() as session:
        uc = await get_update_file_protect_uc(session)
        result = await uc.execute(lookup_key, req_id, is_protect)
        logger.info(
            f"Processed protect request: lookup_key={lookup_key}, req_id={req_id}, is_protect={is_protect}, result={result['status']}"
        )


def build_update_file_protect_stream_worker() -> RedisStreamWorker:
    return RedisStreamWorker(
        stream_key=STREAM_KEY,
        group=GROUP,
        consumer_prefix="file_protect_worker",
        handler=handle_protect_event,
    )