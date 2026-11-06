import asyncio

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from app.infrastructure.db.base import Base
from tests.databases import alembic_config, disposable_postgres_database

pytestmark = pytest.mark.postgres


@pytest.fixture
def empty_database(postgres_admin_url: str):
    with disposable_postgres_database(postgres_admin_url, "messenger_migrations") as url:
        yield url


async def _inspect(url: str, callback):
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        result = await conn.run_sync(callback)
    await engine.dispose()
    return result


def _schema_diff(connection) -> list:
    return compare_metadata(MigrationContext.configure(connection), Base.metadata)


def _tables(connection) -> set[str]:
    return set(inspect(connection).get_table_names())


def test_single_alembic_head() -> None:
    assert len(ScriptDirectory.from_config(alembic_config("sqlite://")).get_heads()) == 1


async def test_upgrade_head_then_downgrade_one_step_then_upgrade(empty_database: str) -> None:
    config = alembic_config(empty_database)
    await asyncio.to_thread(command.upgrade, config, "head")
    assert await _inspect(empty_database, _schema_diff) == []
    await asyncio.to_thread(command.downgrade, config, "-1")
    await asyncio.to_thread(command.upgrade, config, "head")
    assert await _inspect(empty_database, _schema_diff) == []
    assert "artifacts" in await _inspect(empty_database, _tables)


async def test_full_downgrade_to_base_leaves_no_tables(empty_database: str) -> None:
    config = alembic_config(empty_database)
    await asyncio.to_thread(command.upgrade, config, "head")
    await asyncio.to_thread(command.downgrade, config, "base")
    assert await _inspect(empty_database, _tables) == {"alembic_version"}
