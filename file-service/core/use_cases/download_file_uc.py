from typing import Optional
from core.entities.file_metadata import FileMetadata
from core.interfaces.file_repository import IFileRepository
from core.interfaces.metadata_store import IMetadataStore
from core.interfaces.file_storage import IFileStorage
from core.interfaces.signature_verifier import ISignatureVerifier
from core.interfaces.download_access_store import IDownloadAccessStore


class DownloadFileUC:
    def __init__(
        self,
        file_repo: IFileRepository,
        metadata_store: IMetadataStore,
        file_storage: IFileStorage,
        signature_verifier: ISignatureVerifier,
        download_access_store: IDownloadAccessStore,
    ):
        self.file_repo = file_repo
        self.metadata_store = metadata_store
        self.file_storage = file_storage
        self.signature_verifier = signature_verifier
        self.download_access_store = download_access_store

    async def execute(
        self,
        lookup_key: str,
        chunk_number: int,
        public_id: str,
        signature: Optional[str] = None,
    ) -> bytes:

        cached_results = await self.metadata_store.get_batch([lookup_key])
        metadata: Optional[FileMetadata] = cached_results[0]

        if not metadata:
            db_results = await self.file_repo.get_metadata_batch([lookup_key])
            if not db_results:
                raise FileNotFoundError(f"File not found: {lookup_key}")
            metadata = db_results[0]
            await self.metadata_store.set(metadata)

        if metadata.is_private:
            already_allowed = await self.download_access_store.is_allowed(public_id, lookup_key)
            if not already_allowed:
                if not signature:
                    raise PermissionError("Signature required for private file")
                ok = await self.signature_verifier.verify(signature, metadata.lookup_key)
                if not ok:
                    raise PermissionError("Invalid signature")
                await self.download_access_store.allow(public_id, lookup_key)

        return await self.file_storage.get_chunk(metadata.id, chunk_number)