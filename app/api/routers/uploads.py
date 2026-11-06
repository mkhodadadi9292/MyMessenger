from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user, get_settings, get_upload_service
from app.application.upload_service import UploadService
from app.config import Settings
from app.domain.entities import User
from app.domain.uploads import UploadRequest
from app.domain.value_objects import ArtifactKind

router = APIRouter(tags=["uploads"])


class UploadTicketIn(BaseModel):
    file_name: str
    size_bytes: int
    mime_type: str
    kind: ArtifactKind
    sha256: str
    reply_to_id: int | None = None


class UploadTicketOut(BaseModel):
    upload_id: str
    ticket: str
    upload_url: str
    expires_at: datetime


@router.post("/chats/{chat_id}/uploads", status_code=201, response_model=UploadTicketOut)
async def request_upload(
    chat_id: int,
    body: UploadTicketIn,
    current_user: User = Depends(get_current_user),
    service: UploadService = Depends(get_upload_service),
    settings: Settings = Depends(get_settings),
) -> UploadTicketOut:
    issued = await service.request_upload(
        current_user.id,
        chat_id,
        UploadRequest(
            file_name=body.file_name,
            size_bytes=body.size_bytes,
            mime_type=body.mime_type,
            kind=body.kind,
            sha256=body.sha256,
            reply_to_id=body.reply_to_id,
        ),
    )
    return UploadTicketOut(
        upload_id=issued.upload_id,
        ticket=issued.token,
        upload_url=settings.file_service_upload_url,
        expires_at=issued.expires_at,
    )
