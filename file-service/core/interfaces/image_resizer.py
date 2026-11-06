class IImageResizer:
    async def resize(self, session_id: str, width: int, height: int) -> str:
        raise NotImplementedError
