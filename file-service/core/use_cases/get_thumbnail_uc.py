from core.interfaces.thumbnail_service import IThumbnailService


class GetThumbnailUC:
    def __init__(self, thumbnail_service: IThumbnailService):
        self.thumbnail_service = thumbnail_service

    async def execute(self, session_id: str) -> bytes:
        return await self.thumbnail_service.get_thumbnail(session_id)
