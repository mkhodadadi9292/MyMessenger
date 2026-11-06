import asyncio
import hashlib
import os
import shutil
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

from file_service.domain.exceptions import PayloadTooLargeError, ValidationError
from file_service.domain.media_type import EXTENSION_BY_MIME, SNIFF_BYTES
from file_service.domain.ports import AssemblyResult, ChunkStore, MediaStore

ASSEMBLY_READ_SIZE = 1024 * 1024
ARTIFACTS_DIR = "artifacts"


class LocalChunkStore(ChunkStore):
    def __init__(self, root: Path) -> None:
        self._root = root

    def _upload_dir(self, upload_id: str) -> Path:
        return self._root / upload_id

    async def write(
        self, upload_id: str, index: int, body: AsyncIterator[bytes], expected_length: int
    ) -> None:
        directory = self._upload_dir(upload_id)
        directory.mkdir(parents=True, exist_ok=True)
        final = directory / f"{index}.part"
        partial = directory / f"{index}.{uuid.uuid4().hex}.tmp"
        written = 0
        try:
            with partial.open("wb") as handle:
                async for piece in body:
                    written += len(piece)
                    if written > expected_length:
                        raise PayloadTooLargeError(f"chunk {index} is larger than declared")
                    handle.write(piece)
            if written != expected_length:
                raise ValidationError(f"chunk {index} is shorter than declared")
            os.replace(partial, final)
        finally:
            partial.unlink(missing_ok=True)

    def received(self, upload_id: str) -> set[int]:
        directory = self._upload_dir(upload_id)
        if not directory.is_dir():
            return set()
        return {int(p.stem) for p in directory.glob("*.part") if p.stem.isdigit()}

    def chunk_paths(self, upload_id: str, total_chunks: int) -> list[str]:
        directory = self._upload_dir(upload_id)
        return [str(directory / f"{index}.part") for index in range(total_chunks)]

    def delete(self, upload_id: str) -> None:
        shutil.rmtree(self._upload_dir(upload_id), ignore_errors=True)

    def list_upload_dirs(self, older_than: datetime) -> list[str]:
        if not self._root.is_dir():
            return []
        cutoff = older_than.replace(tzinfo=UTC).timestamp()
        return sorted(
            entry.name
            for entry in self._root.iterdir()
            if entry.is_dir() and entry.stat().st_mtime < cutoff
        )


class LocalMediaStore(MediaStore):
    def __init__(self, media_root: Path) -> None:
        self._root = media_root

    def _partial_path(self, upload_id: str) -> Path:
        return self._root / ARTIFACTS_DIR / f".{upload_id}.partial"

    def allocate_path(self, mime_type: str) -> str:
        return f"{ARTIFACTS_DIR}/{uuid.uuid4().hex}{EXTENSION_BY_MIME[mime_type]}"

    async def assemble(self, upload_id: str, chunk_paths: list[str]) -> AssemblyResult:
        return await asyncio.to_thread(self._assemble, upload_id, chunk_paths)

    def _assemble(self, upload_id: str, chunk_paths: list[str]) -> AssemblyResult:
        target = self._partial_path(upload_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        head = b""
        with target.open("wb") as out:
            for chunk_path in chunk_paths:
                with open(chunk_path, "rb") as source:
                    while piece := source.read(ASSEMBLY_READ_SIZE):
                        if len(head) < SNIFF_BYTES:
                            head += piece[: SNIFF_BYTES - len(head)]
                        digest.update(piece)
                        size += len(piece)
                        out.write(piece)
            out.flush()
            os.fsync(out.fileno())
        return AssemblyResult(size_bytes=size, sha256=digest.hexdigest(), head=head)

    def publish(self, upload_id: str, file_path: str) -> None:
        os.replace(self._partial_path(upload_id), self._root / file_path)

    def discard(self, upload_id: str, file_path: str | None) -> None:
        self._partial_path(upload_id).unlink(missing_ok=True)
        if file_path is not None:
            (self._root / file_path).unlink(missing_ok=True)
