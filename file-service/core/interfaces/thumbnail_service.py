class IThumbnailService:
    async def generate_image_thumbnail(self, session_id: str) -> bool:
        raise NotImplementedError

    async def generate_video_thumbnail(self, session_id: str) -> bool:
        raise NotImplementedError

    async def generate_audio_thumbnail(self, session_id: str, file_ext: str | None = None) -> bool:
        raise NotImplementedError

    async def delete_thumbnail(self, session_id):
        raise NotImplementedError

    async def get_thumbnail(self, session_id: str) -> bytes:
        raise NotImplementedError
