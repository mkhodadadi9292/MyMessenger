import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

from file_service.domain.chunk_plan import ChunkPlan
from file_service.domain.events import UploadCompleted
from file_service.domain.exceptions import (
    ConflictError,
    LengthRequiredError,
    MissingChunksError,
    NotFoundError,
    PayloadTooLargeError,
    UnauthorizedError,
    ValidationError,
    VerificationError,
)
from file_service.domain.media_type import ALLOWED_MIME_TYPES, content_matches_declared_type
from file_service.domain.ports import (
    ChunkStore,
    Clock,
    CompletionPublisher,
    MediaStore,
    TicketVerifier,
    Transaction,
    UploadSessionRepository,
)
from file_service.domain.ticket import UploadTicket
from file_service.domain.upload_session import UploadSession, UploadStatus

logger = logging.getLogger("file_service.uploads")


@dataclass(frozen=True)
class UploadState:
    session: UploadSession
    received_chunks: list[int]
    expires_at: int | None = None


class UploadService:
    def __init__(
        self,
        sessions: UploadSessionRepository,
        transaction: Transaction,
        chunks: ChunkStore,
        media: MediaStore,
        tickets: TicketVerifier,
        publisher: CompletionPublisher | None,
        clock: Clock,
        chunk_size: int,
        max_upload_size_bytes: int,
    ) -> None:
        self._sessions = sessions
        self._transaction = transaction
        self._chunks = chunks
        self._media = media
        self._tickets = tickets
        self._publisher = publisher
        self._clock = clock
        self._chunk_size = chunk_size
        self._max_upload_size_bytes = max_upload_size_bytes

    def _ticket_for(self, token: str, upload_id: str | None = None) -> UploadTicket:
        ticket = self._tickets.verify(token)
        if upload_id is not None:
            ticket.require_upload(upload_id)
        return ticket

    async def _owned_session(self, ticket: UploadTicket) -> UploadSession:
        session = await self._sessions.get(ticket.upload_id)
        if session is None:
            raise NotFoundError("upload not found")
        if session.user_id != ticket.user_id:
            raise UnauthorizedError("ticket does not belong to this upload")
        return session

    def _state(self, session: UploadSession) -> UploadState:
        if session.is_finished:
            received = list(range(session.total_chunks))
        elif session.status is UploadStatus.ACTIVE:
            received = sorted(self._chunks.received(session.upload_id))
        else:
            received = []
        return UploadState(session=session, received_chunks=received)

    async def init(self, token: str) -> tuple[UploadState, bool]:
        ticket = self._ticket_for(token)
        if ticket.size_bytes > self._max_upload_size_bytes:
            raise PayloadTooLargeError("upload is larger than this service accepts")
        if ticket.mime_type not in ALLOWED_MIME_TYPES:
            raise ValidationError(f"unsupported mime type: {ticket.mime_type}")
        existing = await self._sessions.get(ticket.upload_id)
        if existing is None:
            now = self._clock.now()
            plan = ChunkPlan(ticket.size_bytes, self._chunk_size)
            candidate = UploadSession(
                upload_id=ticket.upload_id,
                user_id=ticket.user_id,
                mime_type=ticket.mime_type,
                size_bytes=ticket.size_bytes,
                sha256=ticket.sha256,
                chunk_size=plan.chunk_size,
                total_chunks=plan.total_chunks,
                status=UploadStatus.ACTIVE,
                ticket=ticket.raw,
                created_at=now,
                last_activity_at=now,
            )
            if await self._sessions.add(candidate):
                await self._transaction.commit()
                return self._state(candidate), True
            await self._transaction.rollback()
            existing = await self._sessions.get(ticket.upload_id)
            if existing is None:
                raise ConflictError("upload could not be created")
        if existing.user_id != ticket.user_id:
            raise UnauthorizedError("ticket does not belong to this upload")
        if existing.status is not UploadStatus.ACTIVE:
            raise ConflictError(f"upload is already {existing.status.value}")
        return self._state(existing), False

    async def put_chunk(
        self,
        token: str,
        upload_id: str,
        index: int,
        content_length: int | None,
        body: AsyncIterator[bytes],
    ) -> int:
        ticket = self._ticket_for(token, upload_id)
        session = await self._owned_session(ticket)
        if session.status is not UploadStatus.ACTIVE:
            raise ConflictError(f"upload is {session.status.value}")
        expected = session.plan.expected_length(index)
        if content_length is None:
            raise LengthRequiredError("Content-Length is required")
        if content_length > expected:
            raise PayloadTooLargeError(f"chunk {index} must be {expected} bytes")
        if content_length < expected:
            raise ValidationError(f"chunk {index} must be {expected} bytes")
        await self._chunks.write(upload_id, index, body, expected)
        await self._sessions.touch(upload_id, self._clock.now())
        await self._transaction.commit()
        return expected

    async def status(self, token: str, upload_id: str) -> UploadState:
        ticket = self._ticket_for(token, upload_id)
        return self._state(await self._owned_session(ticket))

    async def complete(self, token: str, upload_id: str) -> UploadState:
        ticket = self._ticket_for(token, upload_id)
        session = await self._owned_session(ticket)
        if session.is_finished:
            return self._state(session)
        if session.status is not UploadStatus.ACTIVE:
            raise ConflictError(f"upload is {session.status.value}")
        missing = session.plan.missing(self._chunks.received(upload_id))
        if missing:
            raise MissingChunksError(missing)
        file_path = self._media.allocate_path(session.mime_type)
        started = await self._sessions.transition(
            upload_id,
            [UploadStatus.ACTIVE],
            UploadStatus.ASSEMBLING,
            self._clock.now(),
            file_path=file_path,
        )
        await self._transaction.commit()
        if not started:
            raise ConflictError("upload is already being completed")
        result = await self._media.assemble(
            upload_id, self._chunks.chunk_paths(upload_id, session.total_chunks)
        )
        failure = self._verification_failure(session, result.size_bytes, result.sha256, result.head)
        if failure is not None:
            self._media.discard(upload_id, file_path)
            self._chunks.delete(upload_id)
            await self._sessions.transition(
                upload_id,
                [UploadStatus.ASSEMBLING],
                UploadStatus.FAILED,
                self._clock.now(),
                failure_reason=failure,
                decided=True,
            )
            await self._transaction.commit()
            raise VerificationError(failure.replace("_", " "))
        self._media.publish(upload_id, file_path)
        await self._sessions.transition(
            upload_id,
            [UploadStatus.ASSEMBLING],
            UploadStatus.COMPLETED,
            self._clock.now(),
            completed=True,
        )
        await self._transaction.commit()
        self._chunks.delete(upload_id)
        completed = await self._sessions.get(upload_id)
        assert completed is not None
        await self.publish_completion(completed)
        return self._state(completed)

    @staticmethod
    def _verification_failure(
        session: UploadSession, size_bytes: int, sha256: str, head: bytes
    ) -> str | None:
        if size_bytes != session.size_bytes:
            return "size_mismatch"
        if sha256 != session.sha256:
            return "checksum_mismatch"
        if not content_matches_declared_type(head, session.mime_type):
            return "mime_mismatch"
        return None

    async def publish_completion(self, session: UploadSession) -> bool:
        if self._publisher is None or session.file_path is None or session.completed_at is None:
            return False
        try:
            event_id = await self._publisher.publish_completed(
                UploadCompleted(
                    upload_id=session.upload_id,
                    ticket=session.ticket,
                    file_path=session.file_path,
                    size_bytes=session.size_bytes,
                    sha256=session.sha256,
                    mime_type=session.mime_type,
                    completed_at=session.completed_at,
                )
            )
        except Exception:
            logger.exception("publishing upload.completed failed for %s", session.upload_id)
            return False
        await self._sessions.mark_published(session.upload_id, event_id)
        await self._transaction.commit()
        return True

    async def abort(self, token: str, upload_id: str) -> None:
        ticket = self._ticket_for(token, upload_id)
        session = await self._owned_session(ticket)
        if session.status in (UploadStatus.ABORTED, UploadStatus.PURGED):
            return
        if session.status is not UploadStatus.ACTIVE:
            raise ConflictError(f"upload is {session.status.value}")
        aborted = await self._sessions.transition(
            upload_id,
            [UploadStatus.ACTIVE],
            UploadStatus.ABORTED,
            self._clock.now(),
            decided=True,
        )
        await self._transaction.commit()
        if not aborted:
            raise ConflictError("upload changed state, try again")
        self._chunks.delete(upload_id)
