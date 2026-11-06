from core.interfaces.file_type_detector import IFileTypeDetector
from core.entities.file_kind import FileKind


class FileTypeDetector(IFileTypeDetector):

    async def detect(self, first_chunk: bytes) -> FileKind:
        if not first_chunk or len(first_chunk) < 4:
            return FileKind.FILE

        # PNG
        if first_chunk.startswith(b"\x89PNG\r\n\x1a\n"):
            return FileKind.IMAGE

        # JPEG / JPG
        if first_chunk.startswith(b"\xff\xd8"):
            return FileKind.IMAGE

        # GIF
        if first_chunk.startswith(b"GIF87a") or first_chunk.startswith(b"GIF89a"):
            return FileKind.IMAGE

        # WEBP
        if first_chunk.startswith(b"RIFF") and b"WEBP" in first_chunk[:12]:
            return FileKind.IMAGE

        # BMP
        if first_chunk.startswith(b"BM"):
            return FileKind.IMAGE

        # SVG
        if first_chunk.lstrip().startswith(b"<svg"):
            return FileKind.IMAGE

        # MP4 / MOV / M4V
        if first_chunk[4:8] == b"ftyp":
            return FileKind.VIDEO

        # WEBM
        if first_chunk.startswith(b"\x1A\x45\xDF\xA3"):
            return FileKind.VIDEO

        # MP3
        if first_chunk.startswith(b"ID3") or first_chunk[:2] == b"\xff\xfb":
            return FileKind.AUDIO

        # WAV
        if first_chunk.startswith(b"RIFF") and b"WAVE" in first_chunk[:12]:
            return FileKind.AUDIO

        # OGG / OPUS
        if first_chunk.startswith(b"OggS"):
            return FileKind.AUDIO

        # FLAC
        if first_chunk.startswith(b"fLaC"):
            return FileKind.AUDIO

        # AAC
        if first_chunk[:2] in (b"\xff\xf1", b"\xff\xf9"):
            return FileKind.AUDIO

        return FileKind.FILE
