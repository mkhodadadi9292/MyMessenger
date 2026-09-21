from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import get_artifact_service, get_current_user
from app.api.schemas.common import message_to_out
from app.application.artifact_service import ArtifactService
from app.domain.entities import User
from app.domain.value_objects import ArtifactKind

router = APIRouter(tags=["artifacts"])


@router.post("/chats/{chat_id}/artifacts")
async def upload_artifact(
    chat_id: int,
    kind: ArtifactKind = Form(...),
    reply_to_id: int | None = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    service: ArtifactService = Depends(get_artifact_service),
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
    return message_to_out(message, current_user, artifact).model_dump()


@router.get("/artifacts/{artifact_id}/download")
async def download_artifact(
    artifact_id: int,
    current_user: User = Depends(get_current_user),
    service: ArtifactService = Depends(get_artifact_service),
) -> FileResponse:
    artifact, path = await service.download(current_user.id, artifact_id)
    return FileResponse(path, media_type=artifact.mime_type, filename=artifact.file_name)
