import os
from collections.abc import AsyncIterator
from datetime import datetime, timedelta

import fakeredis
import httpx
import pytest
from file_service.config import Settings as FileServiceSettings
from file_service.domain.upload_session import UploadStatus
from file_service.infrastructure.clock import utcnow
from file_service.infrastructure.db.base import Base
from file_service.infrastructure.db.models import UploadSessionModel
from file_service.infrastructure.db.repositories import SqlUploadSessionRepository
from file_service.main import create_app
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from file_cleaner.application.scheduler import CleanupScheduler
from file_cleaner.config import Settings as CleanerSettings
from file_cleaner.infrastructure.http_api import HttpCleanupApi

INTERNAL_KEY = "cleaner-test-key"
DAY = 86400


class FileServiceWorld:
    def __init__(self, app, tmp_path) -> None:
        self.app = app
        self.media = tmp_path / "media"
        self.chunks = tmp_path / "uploads"

    async def add(
        self,
        upload_id: str,
        status: UploadStatus,
        age_seconds: float,
        *,
        with_file: bool = False,
        with_chunks: bool = False,
        published: bool = True,
    ) -> str | None:
        when = utcnow() - timedelta(seconds=age_seconds)
        file_path = f"artifacts/{upload_id}.png" if with_file else None
        async with self.app.state.session_factory() as session:
            session.add(
                UploadSessionModel(
                    upload_id=upload_id,
                    user_id=1,
                    mime_type="image/png",
                    size_bytes=4,
                    sha256="0" * 64,
                    chunk_size=4,
                    total_chunks=1,
                    status=status.value,
                    ticket="t",
                    created_at=when,
                    last_activity_at=when,
                    file_path=file_path,
                    completed_event_id="1-0" if published else None,
                    completed_at=when if status is UploadStatus.COMPLETED else None,
                )
            )
            await session.commit()
        if with_file:
            (self.media / file_path).parent.mkdir(parents=True, exist_ok=True)
            (self.media / file_path).write_bytes(b"data")
        if with_chunks:
            self.add_chunk_dir(upload_id, age_seconds)
        return file_path

    def add_chunk_dir(self, upload_id: str, age_seconds: float) -> None:
        directory = self.chunks / upload_id
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "0.part").write_bytes(b"x")
        stamp = (datetime.now() - timedelta(seconds=age_seconds)).timestamp()
        os.utime(directory, (stamp, stamp))

    def has_file(self, file_path: str) -> bool:
        return (self.media / file_path).exists()

    def has_chunks(self, upload_id: str) -> bool:
        return (self.chunks / upload_id).exists()

    async def status(self, upload_id: str) -> UploadStatus:
        async with self.app.state.session_factory() as session:
            return (await SqlUploadSessionRepository(session).get(upload_id)).status

    async def settle_streams(self, settled: bool) -> None:
        redis = self.app.state.redis
        await redis.xgroup_create("upload.completed", "messenger-backend", id="0", mkstream=True)
        await redis.xgroup_create("upload.outcome", "file-service", id="0", mkstream=True)
        if settled:
            entry = await redis.xadd("upload.completed", {"upload_id": "x"})
            await redis.xreadgroup("messenger-backend", "b", {"upload.completed": ">"})
            await redis.xack("upload.completed", "messenger-backend", entry)


@pytest.fixture
async def world(tmp_path) -> AsyncIterator[FileServiceWorld]:
    settings = FileServiceSettings(
        database_url="sqlite+aiosqlite://",
        redis_url=None,
        workers_enabled=False,
        media_root=tmp_path / "media",
        chunks_root=tmp_path / "uploads",
        internal_api_key=INTERNAL_KEY,
        _env_file=None,
    )
    app = create_app(settings)
    await app.state.engine.dispose()
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    app.state.engine = engine
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app.state.redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield FileServiceWorld(app, tmp_path)
    await app.state.redis.aclose()
    await engine.dispose()


async def run_cleaner(world: FileServiceWorld, **overrides) -> dict[str, list[str]]:
    settings = CleanerSettings(_env_file=None, internal_api_key=INTERNAL_KEY, **overrides)
    transport = httpx.ASGITransport(app=world.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://file-service") as client:
        scheduler = CleanupScheduler(
            HttpCleanupApi(client, settings.internal_api_key), settings.policies(), 100
        )
        reports = await scheduler.run_due(now=0)
    return {report.rule.value: report.purged for report in reports}


async def test_stale_incomplete_session_loses_its_chunks(world: FileServiceWorld) -> None:
    await world.add("a" * 32, UploadStatus.ACTIVE, 2 * DAY, with_chunks=True)
    await world.add("b" * 32, UploadStatus.ACTIVE, 60, with_chunks=True)
    purged = await run_cleaner(world)
    assert purged["stale-active"] == ["a" * 32]
    assert not world.has_chunks("a" * 32)
    assert world.has_chunks("b" * 32)


async def test_completed_but_never_attached_file_is_removed_after_grace(
    world: FileServiceWorld,
) -> None:
    await world.settle_streams(settled=True)
    old = await world.add("c" * 32, UploadStatus.COMPLETED, 3 * DAY, with_file=True)
    fresh = await world.add("d" * 32, UploadStatus.COMPLETED, 60, with_file=True)
    purged = await run_cleaner(world)
    assert purged["unattached"] == ["c" * 32]
    assert not world.has_file(old)
    assert world.has_file(fresh)


async def test_unattached_file_is_kept_while_streams_are_unsettled(
    world: FileServiceWorld,
) -> None:
    await world.settle_streams(settled=False)
    path = await world.add("e" * 32, UploadStatus.COMPLETED, 3 * DAY, with_file=True)
    purged = await run_cleaner(world)
    assert purged["unattached"] == []
    assert world.has_file(path)


async def test_rejected_upload_file_is_removed(world: FileServiceWorld) -> None:
    path = await world.add("f" * 32, UploadStatus.REJECTED, 3600, with_file=True)
    purged = await run_cleaner(world)
    assert purged["terminal"] == ["f" * 32]
    assert not world.has_file(path)
    assert await world.status("f" * 32) is UploadStatus.PURGED


async def test_leftover_chunk_directories_are_removed(world: FileServiceWorld) -> None:
    world.add_chunk_dir("0" * 32, 2 * 3600)
    world.add_chunk_dir("1" * 32, 60)
    purged = await run_cleaner(world)
    assert purged["orphan-chunk-dirs"] == ["0" * 32]
    assert world.has_chunks("1" * 32)


async def test_stuck_assembly_is_cleaned(world: FileServiceWorld) -> None:
    path = await world.add("2" * 32, UploadStatus.ASSEMBLING, 2 * 3600, with_file=True)
    purged = await run_cleaner(world)
    assert purged["stuck-assembling"] == ["2" * 32]
    assert not world.has_file(path)


async def test_cleaner_never_deletes_referenced_files(world: FileServiceWorld) -> None:
    await world.settle_streams(settled=True)
    referenced = await world.add(
        "3" * 32, UploadStatus.ATTACHED, 365 * DAY, with_file=True, with_chunks=True
    )
    untracked = world.media / "artifacts" / "legacy-upload.png"
    untracked.write_bytes(b"old multipart upload")
    avatar = world.media / "avatars" / "me.png"
    avatar.parent.mkdir(parents=True)
    avatar.write_bytes(b"avatar")
    await run_cleaner(
        world,
        upload_session_ttl_seconds=0,
        assembly_stuck_ttl_seconds=0,
        attach_grace_period_seconds=1,
        backend_upload_event_max_age_seconds=0,
        terminal_purge_delay_seconds=0,
        orphan_chunk_dir_min_age_seconds=0,
    )
    assert world.has_file(referenced)
    assert untracked.exists()
    assert avatar.exists()
    assert await world.status("3" * 32) is UploadStatus.ATTACHED


async def test_cleaner_keeps_everything_when_file_service_is_unreachable() -> None:
    settings = CleanerSettings(_env_file=None, file_service_url="http://127.0.0.1:9")
    async with httpx.AsyncClient(base_url=settings.file_service_url, timeout=1) as client:
        scheduler = CleanupScheduler(HttpCleanupApi(client, "k"), settings.policies(), 10)
        assert await scheduler.run_due(now=0) == []
