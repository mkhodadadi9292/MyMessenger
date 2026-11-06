import asyncio

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from app.infrastructure.db.models import ArtifactModel, MessageModel
from tests.databases import alembic_config, disposable_postgres_database
from tests.fakes import RecordingOutcomePublisher
from tests.helpers import API_V1, auth_headers
from tests.uploads import completed_event, completion_handler, store_like_file_service, ticket_for

pytestmark = pytest.mark.postgres

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture
def suite_database_url(postgres_suite_url: str) -> str:
    return postgres_suite_url


async def test_concurrent_consumers_attach_the_same_upload_once(app, client, user_factory) -> None:
    assert app.state.engine.dialect.name == "postgresql"
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat = await client.post(
        f"{API_V1}/chats/private",
        json={"user_id": alice["user"]["id"]},
        headers=auth_headers(bob["access_token"]),
    )
    upload = await ticket_for(client, alice, chat.json()["id"], "p.png", PNG, "image/png", "image")
    event = completed_event(upload, store_like_file_service(app, PNG, "image/png"))
    publishers = [RecordingOutcomePublisher() for _ in range(4)]
    await asyncio.gather(*(completion_handler(app, p)(event) for p in publishers))
    async with app.state.session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(MessageModel)) == 1
        assert await session.scalar(select(func.count()).select_from(ArtifactModel)) == 1
    attached = {p.attached[0] for p in publishers}
    assert len(attached) == 1
    assert all(p.rejected == [] for p in publishers)


@pytest.fixture
def empty_database(postgres_admin_url: str):
    with disposable_postgres_database(postgres_admin_url, "messenger_rows") as url:
        yield url


async def test_upload_id_migration_keeps_existing_artifacts_valid(empty_database: str) -> None:
    config = alembic_config(empty_database)
    await asyncio.to_thread(command.upgrade, config, "c4e7a1b9d2f3")
    engine = create_async_engine(empty_database)
    async with engine.begin() as conn:
        await conn.execute(text(
            "INSERT INTO users (id, username, first_name, created_at) "
            "VALUES (1, 'old', 'Old', now())"
        ))
        await conn.execute(text(
            "INSERT INTO chats (id, type, is_public, owner_id, created_at) "
            "VALUES (1, 'private', false, 1, now())"
        ))
        for message_id in (1, 2):
            await conn.execute(text(
                "INSERT INTO messages (id, chat_id, sender_id, created_at) "
                f"VALUES ({message_id}, 1, 1, now())"
            ))
            await conn.execute(text(
                "INSERT INTO artifacts (message_id, kind, file_name, file_path, mime_type, "
                f"size_bytes, created_at) VALUES ({message_id}, 'image', 'a.png', "
                f"'artifacts/{message_id}.png', 'image/png', 1, now())"
            ))
    await asyncio.to_thread(command.upgrade, config, "head")
    async with engine.connect() as conn:
        nulls = await conn.scalar(text("SELECT count(*) FROM artifacts WHERE upload_id IS NULL"))
    assert nulls == 2
    await asyncio.to_thread(command.downgrade, config, "-1")
    async with engine.connect() as conn:
        assert await conn.scalar(text("SELECT count(*) FROM artifacts")) == 2
    await engine.dispose()

