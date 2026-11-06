import asyncio
import logging
import signal

import httpx

from file_cleaner.application.scheduler import CleanupScheduler
from file_cleaner.config import Settings, get_settings
from file_cleaner.infrastructure.http_api import HttpCleanupApi


def build_scheduler(settings: Settings, client: httpx.AsyncClient) -> CleanupScheduler:
    return CleanupScheduler(
        HttpCleanupApi(client, settings.internal_api_key),
        settings.policies(),
        settings.batch_limit,
    )


async def run(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s"
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, stop.set)
    async with httpx.AsyncClient(
        base_url=settings.file_service_url, timeout=settings.request_timeout_seconds
    ) as client:
        scheduler = build_scheduler(settings, client)
        logging.getLogger("file_cleaner").info("file-cleaner started")
        await scheduler.run_forever(stop)
