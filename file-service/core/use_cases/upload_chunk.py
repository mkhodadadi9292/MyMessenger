from typing import Optional, Dict, Any
from core.errors.file_errors import HashStateMissingError

from core.interfaces.store import IStore
from core.interfaces.file_repository import IFileRepository
from core.interfaces.file_storage import IFileStorage
from core.interfaces.hasher import IHasher
from core.interfaces.metadata_extractor import IFileMetadataExtractor
from core.interfaces.image_resizer import IImageResizer
from core.interfaces.file_type_detector import IFileTypeDetector
from core.interfaces.hash_store import IHashStateStore
from core.interfaces.thumbnail_service import IThumbnailService

from core.entities.upload_session import UploadSession
from core.entities.file_kind import FileKind


class UploadChunkUseCase:
    def __init__(
        self,
        store: IStore,
        file_repo: IFileRepository,
        storage: IFileStorage,
        hasher: IHasher,
        metadata_extractor: IFileMetadataExtractor,
        image_resizer: IImageResizer,
        file_type_detector: IFileTypeDetector,
        hash_state_store: IHashStateStore,
        thumbnail_service: IThumbnailService,
    ):
        self.store = store
        self.file_repo = file_repo
        self.storage = storage
        self.hasher = hasher
        self.metadata_extractor = metadata_extractor
        self.image_resizer = image_resizer
        self.file_type_detector = file_type_detector
        self.hash_state_store = hash_state_store
        self.thumbnail_service = thumbnail_service

    async def execute(
        self,
        session_id: str,
        public_id: str,
        chunk: bytes,
        chunk_number: int,
        total_chunks: int,
        is_private: bool,
        is_protect: bool,
        resize: dict | None,
        name: str,
    ) -> Dict[str, Any]:

        session: Optional[UploadSession] = await self.store.load(session_id)
        if session is None or session.public_id != public_id:
            return {
                "success": False,
                "reason": "session_not_found",
                "chunk_number": None,
                "lookup_key": None,
            }

        expected_chunk_number = session.last_chunk_number + 1
        if chunk_number != expected_chunk_number:
            return {
                "success": False,
                "reason": "invalid_chunk_number",
                "chunk_number": session.last_chunk_number,
                "lookup_key": None,
            }


        if chunk_number == 1:
            file_kind = await self.file_type_detector.detect(chunk)
            session.file_type = file_kind.value
            session.total_chunks = total_chunks

            await self.file_repo.add_upload_record(session_id)

            if file_kind == FileKind.IMAGE and resize is not None:
                session.hash_in_last = True
                last_hash = None
            else:
                session.hash_in_last = False
                last_hash = ""
                await self.hash_state_store.set_state(session_id, last_hash)
        elif session.hash_in_last:
            last_hash = None
        else:
            last_hash = await self.hash_state_store.get_state(session_id)
            if last_hash is None:
                raise HashStateMissingError(session_id)

        await self.storage.append_chunk(session_id, chunk)

        if not session.hash_in_last:
            last_hash = await self.hasher.update_chunk(last_hash, chunk)
            await self.hash_state_store.set_state(session_id, last_hash)

        session.last_chunk_number = chunk_number

        await self.store.update_session(
            session_id=session.session_id,
            public_id=session.public_id,
            last_chunk_number=session.last_chunk_number,
            hash_in_last=session.hash_in_last,
            file_type=session.file_type,
            total_chunks=session.total_chunks,
        )

        if chunk_number < total_chunks:
            return {
                "success": True,
                "chunk_number": chunk_number,
                "lookup_key": None,
            }

        if session.file_type == FileKind.IMAGE.value:
            thumbnail_created = await self.thumbnail_service.generate_image_thumbnail(session_id)
        elif session.file_type == FileKind.VIDEO.value:
            thumbnail_created = await self.thumbnail_service.generate_video_thumbnail(session_id)
        elif session.file_type == FileKind.AUDIO.value:
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else None
            thumbnail_created = await self.thumbnail_service.generate_audio_thumbnail(session_id, ext)
        else:
            thumbnail_created = False

        metadata = await self.metadata_extractor.extract(session_id)
        size_bytes = metadata["size_bytes"]
        size_class = metadata["size_class"]

        if session.file_type == FileKind.IMAGE.value and resize is not None:
            width = resize.get("width")
            height = resize.get("height")
            if width and height:
                await self.image_resizer.resize(session_id, width, height)

        if session.hash_in_last:
            file_hash = await self.hasher.hash_file(session_id)
        else:
            file_hash = last_hash

        existing_lookup_key = await self.file_repo.find_by_hash(file_hash, is_private)

        if existing_lookup_key is not None:
            await self.storage.delete_file(session_id)
            if thumbnail_created:
                await self.thumbnail_service.delete_thumbnail(session_id)
            await self.store.delete(session_id)
            await self.file_repo.delete_upload_record(session_id)

            return {
                "success": True,
                "chunk_number": chunk_number,
                "lookup_key": existing_lookup_key,
            }

        lookup_key = await self.file_repo.create_file(
            file_hash=file_hash,
            size_bytes=size_bytes,
            size_class=size_class,
            is_private=is_private,
            is_protect=is_protect,
            mime_type=FileKind(session.file_type),
            name=name,
            has_thumbnail=thumbnail_created,
            session_id=session_id,
        )

        await self.store.delete(session_id)
        await self.file_repo.delete_upload_record(session_id)

        return {
            "success": True,
            "chunk_number": chunk_number,
            "lookup_key": lookup_key,
        }