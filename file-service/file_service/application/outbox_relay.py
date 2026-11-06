from datetime import timedelta

from file_service.application.upload_service import UploadService
from file_service.domain.ports import Clock, UploadSessionRepository


class OutboxRelay:
    def __init__(
        self,
        sessions: UploadSessionRepository,
        uploads: UploadService,
        clock: Clock,
        min_age_seconds: int,
        batch_size: int = 100,
    ) -> None:
        self._sessions = sessions
        self._uploads = uploads
        self._clock = clock
        self._min_age = timedelta(seconds=min_age_seconds)
        self._batch_size = batch_size

    async def relay_pending(self) -> int:
        pending = await self._sessions.list_unpublished_completed(
            self._clock.now() - self._min_age, self._batch_size
        )
        published = 0
        for session in pending:
            if await self._uploads.publish_completion(session):
                published += 1
        return published
