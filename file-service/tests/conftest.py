from collections.abc import AsyncIterator, Iterator

import fakeredis
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from file_service.config import Settings
from file_service.infrastructure.db import models  # noqa: F401
from file_service.infrastructure.db.base import Base
from file_service.main import create_app
from tests.containers import postgres_server, redis_server
from tests.helpers import TEST_AUDIENCE, TEST_ISSUER, TEST_TICKET_SECRET

TEST_CHUNK_SIZE = 1024
TEST_INTERNAL_KEY = "test-internal-key"


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite://",
        redis_url=None,
        workers_enabled=False,
        media_root=tmp_path / "media",
        chunks_root=tmp_path / "uploads",
        upload_chunk_size_bytes=TEST_CHUNK_SIZE,
        max_upload_size_bytes=64 * 1024,
        upload_ticket_secret=TEST_TICKET_SECRET,
        upload_ticket_issuer=TEST_ISSUER,
        upload_ticket_audience=TEST_AUDIENCE,
        internal_api_key=TEST_INTERNAL_KEY,
        _env_file=None,
    )


@pytest.fixture
async def fake_redis() -> AsyncIterator[Redis]:
    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
async def app(settings: Settings, fake_redis: Redis) -> AsyncIterator[FastAPI]:
    application = create_app(settings)
    await application.state.engine.dispose()
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    application.state.engine = engine
    application.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    application.state.redis = fake_redis
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield application
    await engine.dispose()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    with redis_server() as url:
        yield url


@pytest.fixture
async def real_redis(redis_url: str) -> AsyncIterator[Redis]:
    client = Redis.from_url(redis_url, decode_responses=True)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


@pytest.fixture(scope="session")
def postgres_admin_url() -> Iterator[str]:
    with postgres_server() as url:
        yield url
