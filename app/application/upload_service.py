import uuid

from app.application.message_service import MessageService
from app.application.ports import UploadTicketCodec
from app.domain.time import utcnow
from app.domain.uploads import IssuedTicket, UploadRequest, UploadTicketClaims


class UploadService:
    def __init__(
        self,
        message_service: MessageService,
        tickets: UploadTicketCodec,
        max_artifact_size_bytes: int,
    ) -> None:
        self._message_service = message_service
        self._tickets = tickets
        self._max_artifact_size_bytes = max_artifact_size_bytes

    async def request_upload(
        self, actor_id: int, chat_id: int, request: UploadRequest
    ) -> IssuedTicket:
        await self._message_service.ensure_can_post(actor_id, chat_id)
        request.validate(self._max_artifact_size_bytes)
        reply_to_id = await self._message_service.resolve_reply(chat_id, request.reply_to_id)
        return self._tickets.issue(
            UploadTicketClaims(
                upload_id=uuid.uuid4().hex,
                user_id=actor_id,
                chat_id=chat_id,
                kind=request.kind,
                mime_type=request.mime_type,
                size_bytes=request.size_bytes,
                sha256=request.sha256,
                file_name=request.file_name,
                reply_to_id=reply_to_id,
                issued_at=utcnow(),
            )
        )
