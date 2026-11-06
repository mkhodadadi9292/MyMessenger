import os
import hashlib
from settings import settings
from core.interfaces.hasher import IHasher

class Hasher(IHasher):

    async def update_chunk(self, last_hash: str | None, chunk: bytes) -> str:
        hasher = hashlib.sha256()
        if last_hash:
            hasher.update(bytes.fromhex(last_hash))
        hasher.update(chunk)
        return hasher.hexdigest()

    async def hash_file(self, session_id: str) -> str:
        file_path = os.path.join(settings.storage_path, "files", session_id)
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
