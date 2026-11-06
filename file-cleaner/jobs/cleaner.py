import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.data.database import SessionLocal
from infrastructure.di.providers import (
    get_cleanup_uploading_files_uc,
    get_delete_uncommitted_files_uc,
    get_delete_expired_files_uc,
)

logger = logging.getLogger("file_cleaner")
logger.setLevel(logging.INFO)

handler = logging.StreamHandler()
handler.setLevel(logging.INFO)

formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)

handler.setFormatter(formatter)
logger.addHandler(handler)


def async_session_factory() -> AsyncSession:
    return SessionLocal()


async def run_cleanup_uploading_files():
    try:
        async with async_session_factory() as session:
            uc = get_cleanup_uploading_files_uc(session)
            await uc.execute()
            logger.info("CleanupUploadingFilesUC executed successfully")
    except Exception as exc:
        logger.error(f"CleanupUploadingFilesUC failed: {exc}")


async def run_delete_uncommitted_files():
    try:
        async with async_session_factory() as session:
            uc = get_delete_uncommitted_files_uc(session)
            await uc.execute()
            logger.info("DeleteUncommittedFilesUC executed successfully")
    except Exception as exc:
        logger.error(f"DeleteUncommittedFilesUC failed: {exc}")


async def run_delete_expired_files():
    try:
        async with async_session_factory() as session:
            uc = get_delete_expired_files_uc(session)
            await uc.execute()
            logger.info("DeleteExpiredFilesUC executed successfully")
    except Exception as exc:
        logger.error(f"DeleteExpiredFilesUC failed: {exc}")


def start_jobs():
    scheduler = AsyncIOScheduler(timezone="Asia/Tehran")

    scheduler.add_job(run_cleanup_uploading_files, "interval", hours=3, max_instances=1, coalesce=True)
    scheduler.add_job(run_delete_uncommitted_files, "cron", hour=20, minute=0, max_instances=1, coalesce=True)
    scheduler.add_job(run_delete_expired_files, "cron", hour=3, minute=0, max_instances=1, coalesce=True)

    scheduler.start()
    logger.info("File cleaner jobs started")
