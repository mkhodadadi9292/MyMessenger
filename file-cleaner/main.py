import asyncio
from jobs.cleaner import start_jobs
import logging

logger = logging.getLogger("file_cleaner")

async def main():
    logger.info("Starting file cleaner service...")
    start_jobs()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
