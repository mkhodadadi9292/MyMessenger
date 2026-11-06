import os
from core.interfaces.metadata_extractor import IFileMetadataExtractor
from core.entities.file_size_class import FileSizeClass
from settings import settings

class LocalFileMetadataExtractor(IFileMetadataExtractor):
    def __init__(self):
        self.storage_path =  settings.storage_path

    async def extract(self, session_id: str) -> dict:
        file_path = os.path.join(self.storage_path, "files", session_id)

        size_bytes = os.path.getsize(file_path)

        if size_bytes < 1_000_000:
            size_class = FileSizeClass.SMALL
        elif size_bytes < 20_000_000:
            size_class = FileSizeClass.MEDIUM
        else:
            size_class = FileSizeClass.LARGE

        return {
            "size_bytes": size_bytes,
            "size_class": size_class.value,
        }
