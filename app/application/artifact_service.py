from app.application.ports import MediaLibrary
from app.domain.entities import Artifact
from app.domain.exceptions import ForbiddenError, NotFoundError
from app.domain.repositories.chat import ChatMemberRepository
from app.domain.repositories.message import ArtifactRepository, MessageRepository


class ArtifactService:
    def __init__(
        self,
        messages: MessageRepository,
        artifacts: ArtifactRepository,
        members: ChatMemberRepository,
        media: MediaLibrary,
    ) -> None:
        self._messages = messages
        self._artifacts = artifacts
        self._members = members
        self._media = media

    async def download(self, actor_id: int, artifact_id: int) -> tuple[Artifact, str]:
        artifact = await self._artifacts.get(artifact_id)
        if artifact is None:
            raise NotFoundError("artifact not found")
        message = await self._messages.get(artifact.message_id)
        if message is None:
            raise NotFoundError("artifact not found")
        member = await self._members.get_pair(message.chat_id, actor_id)
        if member is None:
            raise ForbiddenError("you are not a member of this chat")
        return artifact, str(self._media.path_for(artifact.file_path))
