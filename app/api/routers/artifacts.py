from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.api.deps import get_artifact_service, get_current_user
from app.application.artifact_service import ArtifactService
from app.domain.entities import User

router = APIRouter(tags=["artifacts"])


@router.get("/artifacts/{artifact_id}/download")
async def download_artifact(
    artifact_id: int,
    current_user: User = Depends(get_current_user),
    service: ArtifactService = Depends(get_artifact_service),
) -> FileResponse:
    artifact, path = await service.download(current_user.id, artifact_id)
    return FileResponse(path, media_type=artifact.mime_type, filename=artifact.file_name)
