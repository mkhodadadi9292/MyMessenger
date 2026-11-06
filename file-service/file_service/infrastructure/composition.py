from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from file_service.application.cleanup_service import CleanupService
from file_service.application.outbox_relay import OutboxRelay
from file_service.application.outcome_service import OutcomeService
from file_service.application.upload_service import UploadService
from file_service.config import Settings
from file_service.infrastructure.clock import SystemClock
from file_service.infrastructure.db.repositories import (
    SqlTransaction,
    SqlUploadSessionRepository,
)
from file_service.infrastructure.storage import LocalChunkStore, LocalMediaStore
from file_service.infrastructure.streams import (
    RedisCompletionPublisher,
    RedisStreamSettlement,
)
from file_service.infrastructure.tickets import JwtTicketVerifier


def build_upload_service(
    session: AsyncSession, redis: Redis | None, settings: Settings
) -> UploadService:
    publisher = (
        RedisCompletionPublisher(redis, settings.completed_stream, settings.stream_maxlen)
        if redis is not None
        else None
    )
    return UploadService(
        sessions=SqlUploadSessionRepository(session),
        transaction=SqlTransaction(session),
        chunks=LocalChunkStore(settings.chunks_root),
        media=LocalMediaStore(settings.media_root),
        tickets=JwtTicketVerifier(
            settings.upload_ticket_secret,
            settings.upload_ticket_issuer,
            settings.upload_ticket_audience,
        ),
        publisher=publisher,
        clock=SystemClock(),
        chunk_size=settings.upload_chunk_size_bytes,
        max_upload_size_bytes=settings.max_upload_size_bytes,
    )


def build_outbox_relay(session: AsyncSession, redis: Redis, settings: Settings) -> OutboxRelay:
    return OutboxRelay(
        SqlUploadSessionRepository(session),
        build_upload_service(session, redis, settings),
        SystemClock(),
        settings.outbox_min_age_seconds,
    )


def build_outcome_service(session: AsyncSession) -> OutcomeService:
    return OutcomeService(
        SqlUploadSessionRepository(session), SqlTransaction(session), SystemClock()
    )


def build_cleanup_service(
    session: AsyncSession, redis: Redis, settings: Settings
) -> CleanupService:
    return CleanupService(
        sessions=SqlUploadSessionRepository(session),
        transaction=SqlTransaction(session),
        chunks=LocalChunkStore(settings.chunks_root),
        media=LocalMediaStore(settings.media_root),
        settlement=RedisStreamSettlement(
            redis,
            settings.completed_stream,
            settings.backend_group,
            settings.outcome_stream,
            settings.outcome_group,
        ),
        clock=SystemClock(),
    )
