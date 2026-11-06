from datetime import datetime, timedelta

import pytest

from file_service.application.cleanup_service import CleanupRule, CleanupService
from file_service.domain.upload_session import UploadSession, UploadStatus
from tests.fakes import (
    CountingTransaction,
    FixedClock,
    InMemoryChunkStore,
    InMemoryMediaStore,
    InMemorySessionRepository,
    StaticSettlement,
)

HOUR = 3600


class Harness:
    def __init__(self, settled: bool = True) -> None:
        self.clock = FixedClock(datetime(2026, 1, 10))
        self.sessions = InMemorySessionRepository()
        self.chunks = InMemoryChunkStore()
        self.media = InMemoryMediaStore(self.chunks)
        self.settlement = StaticSettlement(settled)
        self.service = CleanupService(
            self.sessions,
            CountingTransaction(),
            self.chunks,
            self.media,
            self.settlement,
            self.clock,
        )

    def add(
        self,
        upload_id: str,
        status: UploadStatus,
        age_hours: float,
        *,
        with_file: bool = False,
        with_chunks: bool = False,
        event_id: str | None = "1-0",
    ) -> UploadSession:
        when = datetime.fromtimestamp(self.clock.now().timestamp() - age_hours * HOUR)
        file_path = f"artifacts/{upload_id}.png" if with_file else None
        session = UploadSession(
            upload_id=upload_id,
            user_id=1,
            mime_type="image/png",
            size_bytes=10,
            sha256="0" * 64,
            chunk_size=10,
            total_chunks=1,
            status=status,
            ticket="t",
            created_at=when,
            last_activity_at=when,
            file_path=file_path,
            completed_event_id=event_id if status is UploadStatus.COMPLETED else None,
            completed_at=when if status is UploadStatus.COMPLETED else None,
        )
        self.sessions.rows[upload_id] = session
        if with_file:
            self.media.files[file_path] = b"data"
        if with_chunks:
            self.chunks.chunks[upload_id] = {0: b"x"}
            self.chunks.dir_ages[upload_id] = when
        return session

    async def run(self, rule: CleanupRule, older_than_hours: float) -> dict:
        return await self.service.run(rule, int(older_than_hours * HOUR), 100)

    def status(self, upload_id: str) -> UploadStatus:
        return self.sessions.rows[upload_id].status


async def test_stale_active_sessions_lose_their_chunks() -> None:
    h = Harness()
    h.add("old", UploadStatus.ACTIVE, 30, with_chunks=True)
    h.add("fresh", UploadStatus.ACTIVE, 1, with_chunks=True)
    result = await h.run(CleanupRule.STALE_ACTIVE, 24)
    assert result["purged"] == ["old"]
    assert h.status("old") is UploadStatus.PURGED
    assert "old" not in h.chunks.chunks
    assert h.status("fresh") is UploadStatus.ACTIVE
    assert "fresh" in h.chunks.chunks


async def test_stuck_assembly_discards_partial_and_planned_file() -> None:
    h = Harness()
    h.add("stuck", UploadStatus.ASSEMBLING, 2, with_file=True, with_chunks=True)
    result = await h.run(CleanupRule.STUCK_ASSEMBLING, 1)
    assert result["purged"] == ["stuck"]
    assert h.media.files == {}
    assert h.chunks.chunks == {}


async def test_unattached_completed_upload_is_purged_once_streams_are_settled() -> None:
    h = Harness(settled=True)
    h.add("lonely", UploadStatus.COMPLETED, 50, with_file=True)
    result = await h.run(CleanupRule.UNATTACHED, 48)
    assert result["purged"] == ["lonely"]
    assert h.media.files == {}


async def test_unattached_upload_is_kept_while_streams_are_not_settled() -> None:
    h = Harness(settled=False)
    h.add("waiting", UploadStatus.COMPLETED, 50, with_file=True)
    result = await h.run(CleanupRule.UNATTACHED, 48)
    assert result == {"rule": "unattached", "purged": [], "skipped": ["waiting"]}
    assert h.status("waiting") is UploadStatus.COMPLETED
    assert h.media.files


async def test_unattached_upload_without_published_event_is_kept() -> None:
    h = Harness(settled=True)
    h.add("unpublished", UploadStatus.COMPLETED, 50, with_file=True, event_id=None)
    result = await h.run(CleanupRule.UNATTACHED, 48)
    assert result["skipped"] == ["unpublished"]
    assert h.media.files


async def test_completed_upload_inside_grace_period_is_kept() -> None:
    h = Harness(settled=True)
    h.add("recent", UploadStatus.COMPLETED, 10, with_file=True)
    result = await h.run(CleanupRule.UNATTACHED, 48)
    assert result["purged"] == []
    assert h.media.files


@pytest.mark.parametrize(
    "status",
    [UploadStatus.REJECTED, UploadStatus.FAILED, UploadStatus.ABORTED, UploadStatus.EXPIRED],
)
async def test_terminal_uploads_are_purged(status: UploadStatus) -> None:
    h = Harness()
    h.add("done", status, 1, with_file=True, with_chunks=True)
    result = await h.run(CleanupRule.TERMINAL, 0.1)
    assert result["purged"] == ["done"]
    assert h.media.files == {}
    assert h.chunks.chunks == {}


@pytest.mark.parametrize("rule", list(CleanupRule))
async def test_attached_files_are_never_purged_by_any_rule(rule: CleanupRule) -> None:
    h = Harness(settled=True)
    h.add("kept", UploadStatus.ATTACHED, 10_000, with_file=True, with_chunks=True)
    h.chunks.chunks.pop("kept")
    await h.run(rule, 0)
    assert h.status("kept") is UploadStatus.ATTACHED
    assert h.media.files == {"artifacts/kept.png": b"data"}


async def test_orphan_chunk_dirs_without_live_session_are_removed() -> None:
    h = Harness()
    h.add("live", UploadStatus.ACTIVE, 5, with_chunks=True)
    h.add("aborted", UploadStatus.ABORTED, 5, with_chunks=True)
    h.chunks.chunks["unknown"] = {0: b"x"}
    h.chunks.dir_ages["unknown"] = datetime(2026, 1, 1)
    result = await h.run(CleanupRule.ORPHAN_CHUNK_DIRS, 1)
    assert sorted(result["purged"]) == ["aborted", "unknown"]
    assert result["skipped"] == ["live"]
    assert "live" in h.chunks.chunks


def test_chunk_dir_age_uses_utc_regardless_of_local_timezone(tmp_path, monkeypatch) -> None:
    import os
    import time

    from file_service.infrastructure.clock import utcnow
    from file_service.infrastructure.storage import LocalChunkStore

    monkeypatch.setenv("TZ", "Asia/Tehran")
    time.tzset()
    try:
        old = tmp_path / ("a" * 32)
        new = tmp_path / ("b" * 32)
        old.mkdir()
        new.mkdir()
        two_hours_ago = time.time() - 7200
        os.utime(old, (two_hours_ago, two_hours_ago))
        cutoff = utcnow().replace(microsecond=0) - timedelta(hours=1)
        assert LocalChunkStore(tmp_path).list_upload_dirs(cutoff) == ["a" * 32]
    finally:
        monkeypatch.delenv("TZ")
        time.tzset()
