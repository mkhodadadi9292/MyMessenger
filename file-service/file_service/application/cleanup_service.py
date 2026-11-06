import logging
from datetime import timedelta
from enum import StrEnum

from file_service.domain.ports import (
    ChunkStore,
    Clock,
    MediaStore,
    StreamSettlement,
    Transaction,
    UploadSessionRepository,
)
from file_service.domain.upload_session import PURGEABLE_TERMINAL_STATUSES, UploadStatus

logger = logging.getLogger("file_service.cleanup")


class CleanupRule(StrEnum):
    STALE_ACTIVE = "stale-active"
    STUCK_ASSEMBLING = "stuck-assembling"
    UNATTACHED = "unattached"
    TERMINAL = "terminal"
    ORPHAN_CHUNK_DIRS = "orphan-chunk-dirs"


class CleanupService:
    def __init__(
        self,
        sessions: UploadSessionRepository,
        transaction: Transaction,
        chunks: ChunkStore,
        media: MediaStore,
        settlement: StreamSettlement,
        clock: Clock,
    ) -> None:
        self._sessions = sessions
        self._transaction = transaction
        self._chunks = chunks
        self._media = media
        self._settlement = settlement
        self._clock = clock

    async def run(self, rule: CleanupRule, older_than_seconds: int, limit: int) -> dict:
        cutoff = self._clock.now() - timedelta(seconds=older_than_seconds)
        handlers = {
            CleanupRule.STALE_ACTIVE: self._stale_active,
            CleanupRule.STUCK_ASSEMBLING: self._stuck_assembling,
            CleanupRule.UNATTACHED: self._unattached,
            CleanupRule.TERMINAL: self._terminal,
            CleanupRule.ORPHAN_CHUNK_DIRS: self._orphan_chunk_dirs,
        }
        purged, skipped = await handlers[rule](cutoff, limit)
        return {"rule": rule.value, "purged": purged, "skipped": skipped}

    async def _claim_for_purge(self, upload_id, from_statuses, cutoff) -> bool:
        changed = await self._sessions.transition(
            upload_id, from_statuses, UploadStatus.PURGED, self._clock.now(), older_than=cutoff
        )
        await self._transaction.commit()
        return changed

    async def _stale_active(self, cutoff, limit):
        purged, skipped = [], []
        for session in await self._sessions.list_by_status([UploadStatus.ACTIVE], cutoff, limit):
            if await self._claim_for_purge(session.upload_id, [UploadStatus.ACTIVE], cutoff):
                self._chunks.delete(session.upload_id)
                purged.append(session.upload_id)
            else:
                skipped.append(session.upload_id)
        return purged, skipped

    async def _stuck_assembling(self, cutoff, limit):
        purged, skipped = [], []
        for session in await self._sessions.list_by_status(
            [UploadStatus.ASSEMBLING], cutoff, limit
        ):
            if await self._claim_for_purge(session.upload_id, [UploadStatus.ASSEMBLING], cutoff):
                self._media.discard(session.upload_id, session.file_path)
                self._chunks.delete(session.upload_id)
                purged.append(session.upload_id)
            else:
                skipped.append(session.upload_id)
        return purged, skipped

    async def _unattached(self, cutoff, limit):
        purged, skipped = [], []
        for session in await self._sessions.list_by_status(
            [UploadStatus.COMPLETED], cutoff, limit
        ):
            settled = False
            if session.completed_event_id is not None:
                try:
                    settled = await self._settlement.is_settled(
                        session.upload_id, session.completed_event_id
                    )
                except Exception:
                    logger.exception("could not read stream state for %s", session.upload_id)
            if not settled:
                skipped.append(session.upload_id)
                continue
            if await self._claim_for_purge(session.upload_id, [UploadStatus.COMPLETED], cutoff):
                self._media.discard(session.upload_id, session.file_path)
                purged.append(session.upload_id)
            else:
                skipped.append(session.upload_id)
        return purged, skipped

    async def _terminal(self, cutoff, limit):
        purged, skipped = [], []
        for session in await self._sessions.list_by_status(
            PURGEABLE_TERMINAL_STATUSES, cutoff, limit
        ):
            if await self._claim_for_purge(session.upload_id, [session.status], cutoff):
                self._media.discard(session.upload_id, session.file_path)
                self._chunks.delete(session.upload_id)
                purged.append(session.upload_id)
            else:
                skipped.append(session.upload_id)
        return purged, skipped

    async def _orphan_chunk_dirs(self, cutoff, limit):
        purged, skipped = [], []
        for upload_id in self._chunks.list_upload_dirs(cutoff)[:limit]:
            session = await self._sessions.get(upload_id)
            if session is not None and session.status in (
                UploadStatus.ACTIVE,
                UploadStatus.ASSEMBLING,
            ):
                skipped.append(upload_id)
                continue
            self._chunks.delete(upload_id)
            purged.append(upload_id)
        return purged, skipped
