class IFileStorage:
    async def append_chunk(self, session_id: str, chunk: bytes):
        raise NotImplementedError

    async def delete_file(self, session_id):
        raise NotImplementedError

    async def get_chunk(self, session_id: str, chunk_number:int) -> bytes:
        raise NotImplementedError