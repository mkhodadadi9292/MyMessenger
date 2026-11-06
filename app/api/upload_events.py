from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.composition import (
    build_message_service,
    build_messaging_repositories,
    build_upload_attach_service,
)
from app.api.realtime import broadcast_new_message
from app.application.ports import UploadOutcomePublisher
from app.application.upload_attach_service import AttachOutcome
from app.config import Settings
from app.domain.exceptions import DuplicateUploadError
from app.domain.uploads import CompletedUpload, RejectionReason, is_upload_id
from app.infrastructure.realtime import ConnectionManager
from app.infrastructure.streams import PermanentEventError

UPLOAD_COMPLETED = "upload.completed"


class InvalidUploadEventError(PermanentEventError):
    def __init__(self, upload_id: str) -> None:
        super().__init__(f"upload {upload_id} event is malformed")
        self.upload_id = upload_id


def parse_completed_upload(fields: dict[str, str]) -> CompletedUpload:
    if fields.get("type") != UPLOAD_COMPLETED:
        raise PermanentEventError(f"unexpected event type {fields.get('type')!r}")
    upload_id = fields.get("upload_id", "")
    if not is_upload_id(upload_id):
        raise PermanentEventError("event has no valid upload_id")
    try:
        return CompletedUpload(
            upload_id=upload_id,
            ticket=fields["ticket"],
            file_path=fields["file_path"],
            size_bytes=int(fields["size_bytes"]),
            sha256=fields["sha256"],
            mime_type=fields["mime_type"],
        )
    except (KeyError, ValueError) as exc:
        raise InvalidUploadEventError(upload_id) from exc


class UploadCompletedHandler:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        hub: ConnectionManager,
        publisher: UploadOutcomePublisher,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._hub = hub
        self._publisher = publisher
        self._settings = settings

    async def __call__(self, fields: dict[str, str]) -> None:
        try:
            upload = parse_completed_upload(fields)
        except InvalidUploadEventError as exc:
            await self._publisher.publish_rejected(exc.upload_id, RejectionReason.INVALID_EVENT)
            raise
        outcome = await self._attach_and_broadcast(upload)
        if outcome.attached:
            await self._publisher.publish_attached(
                outcome.upload_id, outcome.artifact.message_id, outcome.artifact.id
            )
        else:
            await self._publisher.publish_rejected(outcome.upload_id, outcome.reason or "")

    async def _attach_and_broadcast(self, upload: CompletedUpload) -> AttachOutcome:
        async with self._session_factory() as session:
            repos = build_messaging_repositories(session)
            service = build_upload_attach_service(repos, self._settings)
            try:
                outcome = await service.attach(upload)
                await session.commit()
            except DuplicateUploadError:
                await session.rollback()
                outcome = await service.find_attached(upload.upload_id)
                if outcome is None:
                    raise
            if outcome.attached and outcome.message is not None:
                await broadcast_new_message(
                    self._hub,
                    repos.members,
                    build_message_service(repos),
                    outcome.message,
                    outcome.sender,
                    outcome.message.chat_id,
                    outcome.artifact,
                )
            return outcome

    async def has_attached_artifact(self, fields: dict[str, str]) -> bool:
        upload_id = fields.get("upload_id", "")
        if not is_upload_id(upload_id):
            return False
        async with self._session_factory() as session:
            repos = build_messaging_repositories(session)
            return await repos.artifacts.get_by_upload_id(upload_id) is not None
