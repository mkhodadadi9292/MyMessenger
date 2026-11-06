from core.entities.file_kind import FileKind


class IFileTypeDetector:
    async def detect(self, first_chunk: bytes) -> FileKind:
        raise NotImplementedError
