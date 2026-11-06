from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.data.repositories.cleaner_repository_impl import FileRepository
from infrastructure.redis.redis_client import RedisClient
from infrastructure.redis.file_store_impl import FileStore
from infrastructure.api.cleanup_api_impl import CleanupAPI
from infrastructure.kafka.kafka_client import KafkaClient
from infrastructure.kafka.kafka_publisher import FileCleanerPublisherImpl

from core.use_cases.cleanup_uploading_files_uc import CleanupUploadingFilesUC
from core.use_cases.delete_uncommitted_files_uc import DeleteUncommittedFilesUC
from core.use_cases.delete_expired_files_uc import DeleteExpiredFilesUC

redis_client = RedisClient()
file_store = FileStore(redis_client)

cleanup_api = CleanupAPI()

kafka_client = KafkaClient()
file_cleaner_publisher = FileCleanerPublisherImpl(kafka_client)


def get_file_repository(session: AsyncSession):
    return FileRepository(session)


def get_cleanup_uploading_files_uc(session: AsyncSession) -> CleanupUploadingFilesUC:
    return CleanupUploadingFilesUC(
        repo=get_file_repository(session),
        store=file_store,
        api=cleanup_api,
    )


def get_delete_uncommitted_files_uc(session: AsyncSession) -> DeleteUncommittedFilesUC:
    return DeleteUncommittedFilesUC(
        repo=get_file_repository(session),
        api=cleanup_api,
        publisher=file_cleaner_publisher,
        threshold_minutes=60,
    )


def get_delete_expired_files_uc(session: AsyncSession) -> DeleteExpiredFilesUC:
    return DeleteExpiredFilesUC(
        repo=get_file_repository(session),
        api=cleanup_api,
        publisher=file_cleaner_publisher,
    )
