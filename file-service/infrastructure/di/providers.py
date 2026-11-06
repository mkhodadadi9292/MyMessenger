from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.redis.block_store_impl import RedisBlockStoreImpl
from infrastructure.redis.redis_client import RedisClient
from infrastructure.redis.store import RedisStore
from infrastructure.redis.hash_state_store import RedisHashStateStore
from infrastructure.redis.download_access_store_impl import RedisDownloadAccessStore

from infrastructure.data.repositories.file_repository_impl import FileRepository
from core.use_cases.delete_file_by_lookupkey_uc import DeleteFileByLookupKeyUseCase
from infrastructure.file_processing.file_storage_impl import FileStorage
from infrastructure.file_processing.file_type_detector_impl import FileTypeDetector
from infrastructure.file_processing.hasher_impl import Hasher
from infrastructure.file_processing.metadata_extractor_impl import LocalFileMetadataExtractor
from infrastructure.file_processing.image_resizer_impl import LocalImageResizer
from infrastructure.file_processing.thumbnail_service_impl import LocalThumbnailService
from infrastructure.redis.redis_metadata_store import RedisMetadataStore
from infrastructure.security.signature_verifier_impl import SignatureVerifier

from core.use_cases.start_upload import StartUploadUseCase
from core.use_cases.upload_chunk import UploadChunkUseCase
from core.use_cases.delete_file_by_session_uc import DeleteFileBySessionUseCase
from core.use_cases.get_files_metadata_batch_uc import GetFilesMetadataBatchUC
from core.use_cases.get_thumbnail_uc import GetThumbnailUC
from core.use_cases.commit_file_uc import CommitFileUC
from core.use_cases.download_file_uc import DownloadFileUC
from core.use_cases.delete_file_by_session_cleanup_uc import DeleteFileBySessionCleanupUC
from core.use_cases.update_file_protect_uc import UpdateFileProtectUC

redis_client = RedisClient()

file_storage = FileStorage()
file_type_detector = FileTypeDetector()
hasher = Hasher()
metadata_extractor = LocalFileMetadataExtractor()
image_resizer = LocalImageResizer()
thumbnail_service = LocalThumbnailService()


def get_file_repository(session: AsyncSession):
    return FileRepository(session)


async def get_start_upload_uc() -> StartUploadUseCase:
    client = await redis_client.get_client()
    store = RedisStore(client)
    return StartUploadUseCase(store)


async def get_upload_chunk_uc(session: AsyncSession) -> UploadChunkUseCase:
    client = await redis_client.get_client()

    store = RedisStore(client)
    hash_state_store = RedisHashStateStore(client)

    return UploadChunkUseCase(
        store=store,
        file_repo=get_file_repository(session),
        storage=file_storage,
        hasher=hasher,
        metadata_extractor=metadata_extractor,
        image_resizer=image_resizer,
        file_type_detector=file_type_detector,
        hash_state_store=hash_state_store,
        thumbnail_service=thumbnail_service,
    )


def get_delete_file_by_session_uc(session: AsyncSession) -> DeleteFileBySessionUseCase:
    return DeleteFileBySessionUseCase(
        storage=file_storage,
        file_repo=get_file_repository(session),
        thumbnail_service=thumbnail_service,
    )


async def get_delete_file_by_lookupkey_uc(session: AsyncSession):
    client = await redis_client.get_client()
    block_store = RedisBlockStoreImpl(client, scope="delete_block")

    return DeleteFileByLookupKeyUseCase(
        storage=file_storage,
        file_repo=get_file_repository(session),
        thumbnail_service=thumbnail_service,
        block_store=block_store,
    )


async def get_files_metadata_batch_uc(session: AsyncSession) -> GetFilesMetadataBatchUC:
    client = await redis_client.get_client()
    metadata_store = RedisMetadataStore(client)

    return GetFilesMetadataBatchUC(
        file_repo=get_file_repository(session),
        metadata_store=metadata_store,
    )


def get_thumbnail_uc() -> GetThumbnailUC:
    return GetThumbnailUC(thumbnail_service=thumbnail_service)


def get_commit_file_uc(session: AsyncSession) -> CommitFileUC:
    return CommitFileUC(
        file_repo=get_file_repository(session)
    )


async def get_download_file_uc(session: AsyncSession) -> DownloadFileUC:
    client = await redis_client.get_client()
    metadata_store = RedisMetadataStore(client)
    download_access_store = RedisDownloadAccessStore(client)

    return DownloadFileUC(
        file_repo=get_file_repository(session),
        metadata_store=metadata_store,
        file_storage=file_storage,
        signature_verifier=SignatureVerifier(),
        download_access_store=download_access_store,
    )

async def get_update_file_protect_uc(session: AsyncSession) -> UpdateFileProtectUC:
    client = await redis_client.get_client()
    block_store = RedisBlockStoreImpl(client, scope="protect_block")
    return UpdateFileProtectUC(
        file_repo=get_file_repository(session),
        block_store=block_store,
    )


def get_delete_file_by_session_cleanup_uc(session: AsyncSession) -> DeleteFileBySessionCleanupUC:
    return DeleteFileBySessionCleanupUC(
        storage=file_storage,
        file_repo=get_file_repository(session),
        thumbnail_service=thumbnail_service,
    )
