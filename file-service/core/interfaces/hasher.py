from typing import Optional

class IHasher:
    async def update_chunk(self, last_hash: Optional[str], chunk: bytes) -> str:
        raise NotImplementedError

    async def hash_file(self, session_id: str) -> str:
        raise NotImplementedError
