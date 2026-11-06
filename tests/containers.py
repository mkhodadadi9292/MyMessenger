import os
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

POSTGRES_IMAGE = "postgres:17-alpine"
REDIS_IMAGE = "redis:7-alpine"


def _docker_failure(service: str, env_var: str, exc: Exception) -> None:
    pytest.fail(
        f"{service} tests need Docker (testcontainers) or {env_var} pointing at a disposable "
        f"{service} instance. Docker error: {exc}",
        pytrace=False,
    )


@contextmanager
def postgres_server() -> Iterator[str]:
    url = os.environ.get("TEST_POSTGRES_URL")
    if url:
        yield url
        return
    from testcontainers.community.postgres import PostgresContainer

    container = PostgresContainer(
        POSTGRES_IMAGE, username="test", password="test", dbname="postgres", driver="asyncpg"
    )
    try:
        container.start()
    except Exception as exc:
        _docker_failure("Postgres", "TEST_POSTGRES_URL", exc)
    try:
        yield container.get_connection_url()
    finally:
        container.stop()


@contextmanager
def redis_server() -> Iterator[str]:
    url = os.environ.get("TEST_REDIS_URL")
    if url:
        yield url
        return
    from testcontainers.community.redis import RedisContainer

    container = RedisContainer(REDIS_IMAGE)
    try:
        container.start()
    except Exception as exc:
        _docker_failure("Redis", "TEST_REDIS_URL", exc)
    try:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"
    finally:
        container.stop()
