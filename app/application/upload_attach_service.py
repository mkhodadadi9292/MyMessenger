from dataclasses import dataclass
from datetime import timedelta

from app.application.message_service import MessageService
from app.application.ports import MediaLibrary, UploadTicketCodec
from app.domain.entities import Artifact, Message, User
from app.domain.exceptions import (
    BlockedError,
    NotFoundError,
    NotMemberError,
    UnauthorizedError,
    ValidationError,
)
from app.domain.repositories.message import ArtifactRepository, MessageRepository
from app.domain.repositories.user import UserRepository
from app.domain.time import utcnow
from app.domain.uploads import (
    CompletedUpload,
    RejectionReason,
    UploadTicketClaims,
    is_stored_artifact_path,
)


@dataclass(frozen=True)
class AttachOutcome:
    upload_id: str
    reason: str | None = None
    message: Message | None = None
    artifact: Artifact | None = None
    sender: User | None = None
    created: bool = False

    @property
    def attached(self) -> bool:
        return self.artifact is not None


class UploadAttachService:
    def __init__(
        self,
        messages: MessageRepository,
        artifacts: ArtifactRepository,
        users: UserRepository,
        message_service: MessageService,
        tickets: UploadTicketCodec,
        media: MediaLibrary,
        max_event_age_seconds: int,
    ) -> None:
        self._messages = messages
        self._artifacts = artifacts
        self._users = users
        self._message_service = message_service
        self._tickets = tickets
        self._media = media
        self._max_event_age = timedelta(seconds=max_event_age_seconds)

    async def attach(self, upload: CompletedUpload) -> AttachOutcome:
        try:
            claims = self._tickets.read(upload.ticket)
        except UnauthorizedError:
            return AttachOutcome(upload.upload_id, reason=RejectionReason.INVALID_TICKET)
        if not self._matches_ticket(upload, claims):
            return AttachOutcome(upload.upload_id, reason=RejectionReason.INVALID_EVENT)
        existing = await self.find_attached(upload.upload_id)
        if existing is not None:
            return existing
        if utcnow() - claims.issued_at > self._max_event_age:
            return AttachOutcome(upload.upload_id, reason=RejectionReason.TOO_OLD)
        denial = await self._posting_denial(claims)
        if denial is not None:
            return AttachOutcome(upload.upload_id, reason=denial)
        message = await self._messages.add(
            Message(
                id=0,
                chat_id=claims.chat_id,
                sender_id=claims.user_id,
                text=None,
                reply_to_id=await self._reply_target(claims),
                edited_at=None,
                deleted_at=None,
                created_at=utcnow(),
            )
        )
        artifact = await self._artifacts.add(
            Artifact(
                id=0,
                message_id=message.id,
                kind=claims.kind,
                file_name=claims.file_name,
                file_path=upload.file_path,
                mime_type=claims.mime_type,
                size_bytes=claims.size_bytes,
                created_at=utcnow(),
                upload_id=claims.upload_id,
            )
        )
        sender = await self._users.get(claims.user_id)
        return AttachOutcome(
            upload.upload_id, message=message, artifact=artifact, sender=sender, created=True
        )

    async def find_attached(self, upload_id: str) -> AttachOutcome | None:
        artifact = await self._artifacts.get_by_upload_id(upload_id)
        if artifact is None:
            return None
        message = await self._messages.get(artifact.message_id)
        sender = await self._users.get(message.sender_id) if message else None
        return AttachOutcome(upload_id, message=message, artifact=artifact, sender=sender)

    def _matches_ticket(self, upload: CompletedUpload, claims: UploadTicketClaims) -> bool:
        return (
            claims.upload_id == upload.upload_id
            and claims.size_bytes == upload.size_bytes
            and claims.sha256 == upload.sha256
            and claims.mime_type == upload.mime_type
            and is_stored_artifact_path(upload.file_path)
            and self._media.exists(upload.file_path)
        )

    async def _posting_denial(self, claims: UploadTicketClaims) -> str | None:
        try:
            await self._message_service.ensure_can_post(claims.user_id, claims.chat_id)
        except NotFoundError:
            return RejectionReason.CHAT_NOT_FOUND
        except NotMemberError:
            return RejectionReason.NOT_MEMBER
        except BlockedError:
            return RejectionReason.BLOCKED
        return None

    async def _reply_target(self, claims: UploadTicketClaims) -> int | None:
        try:
            return await self._message_service.resolve_reply(claims.chat_id, claims.reply_to_id)
        except (NotFoundError, ValidationError):
            return None
