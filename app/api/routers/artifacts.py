from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import (
    get_artifact_service,
    get_current_user,
    get_member_repo,
    get_message_service,
)
from app.api.realtime import broadcast_new_message
from app.api.routers.messages import _message_dicts
from app.application.artifact_service import ArtifactService
from app.application.message_service import MessageService
from app.domain.entities import User
from app.infrastructure.repositories.chat import SqlChatMemberRepository
from app.domain.value_objects import ArtifactKind

router = APIRouter(tags=["artifacts"])


@router.post("/chats/{chat_id}/artifacts")
async def upload_artifact(
    chat_id: int,
    request: Request,
    kind: ArtifactKind = Form(...),
    reply_to_id: int | None = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    service: ArtifactService = Depends(get_artifact_service),
    message_service: MessageService = Depends(get_message_service),
    members: SqlChatMemberRepository = Depends(get_member_repo),
) -> dict:
    content = await file.read()
    message, artifact = await service.upload(
        current_user.id,
        chat_id,
        kind,
        file.filename or "artifact",
        file.content_type or "application/octet-stream",
        content,
        reply_to_id,
    )
    payload = (await _message_dicts(message_service, [(message, current_user, artifact)]))[0]
    await broadcast_new_message(
        request.app.state.realtime,
        members,
        message_service,
        message,
        current_user,
        chat_id,
        artifact,
    )
    return payload


@router.get("/artifacts/{artifact_id}/download")
async def download_artifact(
    artifact_id: int,
    current_user: User = Depends(get_current_user),
    service: ArtifactService = Depends(get_artifact_service),
) -> FileResponse:
    artifact, path = await service.download(current_user.id, artifact_id)
    return FileResponse(path, media_type=artifact.mime_type, filename=artifact.file_name)
