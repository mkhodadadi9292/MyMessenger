import asyncio
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.infrastructure.db.base import Base


def alembic_config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    config.attributes["database_url_overridden"] = True
    config.attributes["configure_logger"] = False
    return config


def _database_url(admin_url: str, name: str) -> str:
    base, _, _ = admin_url.rpartition("/")
    return f"{base}/{name}"


async def _run_admin(admin_url: str, statement: str) -> None:
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(text(statement))
    await engine.dispose()


@contextmanager
def disposable_postgres_database(admin_url: str, prefix: str) -> Iterator[str]:
    name = f"{prefix}_{uuid.uuid4().hex[:12]}"
    asyncio.run(_run_admin(admin_url, f'CREATE DATABASE "{name}"'))
    try:
        yield _database_url(admin_url, name)
    finally:
        asyncio.run(_run_admin(admin_url, f'DROP DATABASE "{name}" WITH (FORCE)'))


def truncate_all_statement() -> str:
    tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    return f"TRUNCATE {tables} RESTART IDENTITY CASCADE"
