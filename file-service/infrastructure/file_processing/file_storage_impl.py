import os
from core.interfaces.file_storage import IFileStorage
from settings import settings


class FileStorage(IFileStorage):

    def __init__(self):
        self.files_dir = os.path.join(settings.storage_path, "files")
        self.chunk_size = 1024 * 1024

    async def append_chunk(self, session_id: str, chunk: bytes):
        final_file = os.path.join(self.files_dir, session_id)
        with open(final_file, "ab") as f:
            f.write(chunk)

    async def delete_file(self, session_id: str):
        file_path = os.path.join(self.files_dir, session_id)
        if os.path.exists(file_path):
            os.remove(file_path)

    async def get_chunk(self, session_id: str, chunk_number: int) -> bytes:
        file_path = os.path.join(self.files_dir, session_id)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {session_id}")

        offset = chunk_number * self.chunk_size
        with open(file_path, "rb") as f:
            f.seek(offset)
            return f.read(self.chunk_size)
