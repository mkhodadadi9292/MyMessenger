import asyncio
import itertools
import socket

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app
from tests.fakes import CapturingOtpSender
from tests.helpers import register_user


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        media_root=tmp_path / "media",
        jwt_secret="test-secret",
        _env_file=None,
    )


@pytest.fixture
def otp_sender() -> CapturingOtpSender:
    return CapturingOtpSender()


@pytest.fixture
async def app(settings: Settings, otp_sender: CapturingOtpSender) -> FastAPI:
    application = create_app(settings)
    # Seam for the auth implementation: OTP codes go to this capturing
    # sender instead of the server log.
    application.state.otp_sender = otp_sender
    yield application
    await application.state.engine.dispose()


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client


@pytest.fixture
def user_factory(client: AsyncClient, otp_sender: CapturingOtpSender):
    counter = itertools.count(1)

    async def _register_user(
        username: str | None = None,
        identifier: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> dict:
        n = next(counter)
        return await register_user(
            client,
            otp_sender,
            identifier=identifier or f"user{n}@example.com",
            username=username or f"user{n}",
            first_name=first_name or f"First{n}",
            last_name=last_name,
        )

    return _register_user


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
async def live_server(app: FastAPI) -> str:
    import uvicorn

    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    for _ in range(100):
        if server.started:
            break
        await asyncio.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    await task


@pytest.fixture
async def live_client(live_server: str) -> AsyncClient:
    async with httpx.AsyncClient(base_url=live_server) as http_client:
        yield http_client
