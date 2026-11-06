import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import datetime

import pytest
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from alembic import command
from file_service.domain.upload_session import UploadSession, UploadStatus
from file_service.infrastructure.db.repositories import SqlUploadSessionRepository

pytestmark = pytest.mark.postgres


@pytest.fixture
async def disposable_database(postgres_admin_url: str) -> AsyncIterator[str]:
    name = f"fs_test_{uuid.uuid4().hex[:12]}"
    admin = create_async_engine(postgres_admin_url, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text(f'CREATE DATABASE "{name}"'))
    base, _, _ = postgres_admin_url.rpartition("/")
    yield f"{base}/{name}"
    async with admin.connect() as conn:
        await conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
    await admin.dispose()


def alembic_config(url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    config.attributes["database_url_overridden"] = True
    config.attributes["configure_logger"] = False
    return config


async def table_names(engine: AsyncEngine) -> set[str]:
    async with engine.connect() as conn:
        return set(await conn.run_sync(lambda c: inspect(c).get_table_names()))


async def test_upgrade_downgrade_upgrade(disposable_database: str) -> None:
    config = alembic_config(disposable_database)
    engine = create_async_engine(disposable_database)
    await asyncio.to_thread(command.upgrade, config, "head")
    assert "upload_sessions" in await table_names(engine)
    await asyncio.to_thread(command.downgrade, config, "-1")
    assert "upload_sessions" not in await table_names(engine)
    await asyncio.to_thread(command.upgrade, config, "head")
    assert "upload_sessions" in await table_names(engine)
    await engine.dispose()


async def test_compare_and_set_transition_on_postgres(disposable_database: str) -> None:
    await asyncio.to_thread(command.upgrade, alembic_config(disposable_database), "head")
    engine = create_async_engine(disposable_database)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime(2026, 1, 1)
    async with factory() as session:
        repo = SqlUploadSessionRepository(session)
        candidate = UploadSession(
            upload_id="b" * 32, user_id=1, mime_type="image/png", size_bytes=1,
            sha256="0" * 64, chunk_size=1, total_chunks=1, status=UploadStatus.ACTIVE,
            ticket="t", created_at=now, last_activity_at=now,
        )
        assert await repo.add(candidate)
        await session.commit()
        assert not await repo.add(candidate)
        assert await repo.transition("b" * 32, [UploadStatus.ACTIVE], UploadStatus.ASSEMBLING, now)
        assert not await repo.transition(
            "b" * 32, [UploadStatus.ACTIVE], UploadStatus.ASSEMBLING, now
        )
        await session.commit()
        assert (await repo.get("b" * 32)).status is UploadStatus.ASSEMBLING
    await engine.dispose()
