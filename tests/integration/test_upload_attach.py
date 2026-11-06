import asyncio
import hashlib
import json
import uuid
from datetime import timedelta

import pytest
import websockets
from sqlalchemy import func, select

from app.api.composition import build_upload_ticket_codec
from app.domain.time import utcnow
from app.domain.uploads import UploadTicketClaims
from app.domain.value_objects import ArtifactKind
from app.infrastructure.db.models import ArtifactModel, MessageModel
from app.infrastructure.streams import PermanentEventError
from tests.fakes import RecordingOutcomePublisher
from tests.helpers import API_V1, auth_headers
from tests.uploads import (
    TicketedUpload,
    completed_event,
    completion_handler,
    store_like_file_service,
    ticket_for,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


async def _open_chat(client, alice: dict, bob: dict) -> int:
    response = await client.post(
        f"{API_V1}/chats/private",
        json={"user_id": alice["user"]["id"]},
        headers=auth_headers(bob["access_token"]),
    )
    return response.json()["id"]


async def _counts(app) -> tuple[int, int]:
    async with app.state.session_factory() as session:
        messages = await session.scalar(select(func.count()).select_from(MessageModel))
        artifacts = await session.scalar(select(func.count()).select_from(ArtifactModel))
    return messages, artifacts


async def _ready_upload(app, client, alice, chat_id, **kwargs) -> tuple[TicketedUpload, dict]:
    upload = await ticket_for(
        client, alice, chat_id, "pic.png", PNG, "image/png", "image", **kwargs
    )
    return upload, completed_event(upload, store_like_file_service(app, PNG, "image/png"))


async def test_completion_creates_one_message_and_publishes_attached(
    app, client, user_factory
) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    upload, event = await _ready_upload(app, client, alice, chat_id)
    publisher = RecordingOutcomePublisher()
    await completion_handler(app, publisher)(event)
    assert await _counts(app) == (1, 1)
    [(upload_id, message_id, artifact_id)] = publisher.attached
    assert upload_id == upload.upload_id
    history = (
        await client.get(
            f"{API_V1}/chats/{chat_id}/messages", headers=auth_headers(bob["access_token"])
        )
    ).json()
    assert history[0]["id"] == message_id
    assert history[0]["sender"]["id"] == alice["user"]["id"]
    assert history[0]["artifact"]["id"] == artifact_id
    assert history[0]["artifact"]["url"] == f"/media/{event['file_path']}"
    assert history[0]["reactions"] == []


async def test_duplicate_completion_creates_exactly_one_message(app, client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    _, event = await _ready_upload(app, client, alice, chat_id)
    publisher = RecordingOutcomePublisher()
    handler = completion_handler(app, publisher)
    await handler(event)
    await handler(event)
    assert await _counts(app) == (1, 1)
    assert len(publisher.attached) == 2
    assert publisher.attached[0] == publisher.attached[1]


async def test_member_who_left_the_group_is_rejected(app, client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    group = await client.post(
        f"{API_V1}/chats/groups",
        json={"title": "G", "is_public": True},
        headers=auth_headers(alice["access_token"]),
    )
    group_id = group.json()["id"]
    await client.post(f"{API_V1}/chats/{group_id}/join", headers=auth_headers(bob["access_token"]))
    _, event = await _ready_upload(app, client, bob, group_id)
    left = await client.delete(
        f"{API_V1}/chats/{group_id}/leave", headers=auth_headers(bob["access_token"])
    )
    assert left.status_code == 200, left.text
    publisher = RecordingOutcomePublisher()
    await completion_handler(app, publisher)(event)
    assert await _counts(app) == (0, 0)
    assert publisher.rejected == [(event["upload_id"], "not_member")]


async def test_block_during_upload_is_rejected(app, client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    _, event = await _ready_upload(app, client, alice, chat_id)
    await client.post(
        f"{API_V1}/blocked/{alice['user']['id']}", headers=auth_headers(bob["access_token"])
    )
    publisher = RecordingOutcomePublisher()
    await completion_handler(app, publisher)(event)
    assert await _counts(app) == (0, 0)
    assert publisher.rejected == [(event["upload_id"], "blocked")]


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ({"ticket": "not-a-jwt"}, "invalid_ticket"),
        ({"sha256": "0" * 64}, "invalid_event"),
        ({"size_bytes": "1"}, "invalid_event"),
        ({"mime_type": "image/gif"}, "invalid_event"),
        ({"file_path": "../../etc/passwd"}, "invalid_event"),
        ({"file_path": f"artifacts/{'a' * 32}.png"}, "invalid_event"),
        ({"upload_id": uuid.uuid4().hex}, "invalid_event"),
    ],
)
async def test_untrustworthy_events_are_rejected_without_a_message(
    app, client, user_factory, mutation: dict, reason: str
) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    _, event = await _ready_upload(app, client, alice, chat_id)
    publisher = RecordingOutcomePublisher()
    await completion_handler(app, publisher)({**event, **mutation})
    assert await _counts(app) == (0, 0)
    assert [r for _, r in publisher.rejected] == [reason]


async def test_events_older_than_max_age_are_rejected(app, client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    codec = build_upload_ticket_codec(app.state.settings)
    stale = codec.issue(
        UploadTicketClaims(
            upload_id=uuid.uuid4().hex,
            user_id=alice["user"]["id"],
            chat_id=chat_id,
            kind=ArtifactKind.IMAGE,
            mime_type="image/png",
            size_bytes=len(PNG),
            sha256=hashlib.sha256(PNG).hexdigest(),
            file_name="old.png",
            reply_to_id=None,
            issued_at=utcnow() - timedelta(hours=7),
        )
    )
    upload = TicketedUpload(stale.upload_id, stale.token, PNG, "image/png")
    event = completed_event(upload, store_like_file_service(app, PNG, "image/png"))
    publisher = RecordingOutcomePublisher()
    await completion_handler(app, publisher)(event)
    assert publisher.rejected == [(stale.upload_id, "too_old")]


async def test_missing_reply_target_attaches_without_reply(app, client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    codec = build_upload_ticket_codec(app.state.settings)
    issued = codec.issue(
        UploadTicketClaims(
            upload_id=uuid.uuid4().hex,
            user_id=alice["user"]["id"],
            chat_id=chat_id,
            kind=ArtifactKind.IMAGE,
            mime_type="image/png",
            size_bytes=len(PNG),
            sha256=hashlib.sha256(PNG).hexdigest(),
            file_name="pic.png",
            reply_to_id=424242,
            issued_at=utcnow(),
        )
    )
    upload = TicketedUpload(issued.upload_id, issued.token, PNG, "image/png")
    event = completed_event(upload, store_like_file_service(app, PNG, "image/png"))
    publisher = RecordingOutcomePublisher()
    await completion_handler(app, publisher)(event)
    assert len(publisher.attached) == 1
    async with app.state.session_factory() as session:
        message = await session.scalar(select(MessageModel))
    assert message.reply_to_id is None


async def test_malformed_event_is_rejected_and_dead_lettered(app, client, user_factory) -> None:
    upload_id = uuid.uuid4().hex
    publisher = RecordingOutcomePublisher()
    handler = completion_handler(app, publisher)
    with pytest.raises(PermanentEventError):
        await handler({"type": "upload.completed", "upload_id": upload_id})
    assert publisher.rejected == [(upload_id, "invalid_event")]
    with pytest.raises(PermanentEventError):
        await handler({"type": "something.else", "upload_id": upload_id})
    with pytest.raises(PermanentEventError):
        await handler({"type": "upload.completed", "upload_id": "../x"})


async def test_attached_message_is_broadcast_over_websocket(
    app, live_server, otp_sender
) -> None:
    import httpx

    from tests.helpers import register_user

    async with httpx.AsyncClient(base_url=live_server) as client:
        alice = await register_user(client, otp_sender, "a@example.com", "alice", "Alice")
        bob = await register_user(client, otp_sender, "b@example.com", "bob", "Bob")
        chat_id = await _open_chat(client, alice, bob)
        first = await client.post(
            f"{API_V1}/chats/{chat_id}/messages",
            json={"text": "quote me"},
            headers=auth_headers(bob["access_token"]),
        )
        _, event = await _ready_upload(
            app, client, alice, chat_id, reply_to_id=first.json()["id"]
        )
        url = live_server.replace("http://", "ws://") + f"/ws?token={bob['access_token']}"
        async with websockets.connect(url) as ws:
            await ws.send(json.dumps({"type": "subscribe", "chat_id": chat_id}))
            await ws.send(json.dumps({"type": "ping"}))
            async with asyncio.timeout(5):
                while json.loads(await ws.recv())["type"] != "pong":
                    pass
            await completion_handler(app)(event)
            seen: set[str] = set()
            message = None
            async with asyncio.timeout(5):
                while message is None or "chat.list_changed" not in seen:
                    payload = json.loads(await ws.recv())
                    seen.add(payload["type"])
                    if payload["type"] == "message.new":
                        message = payload["message"]
        assert message["sender"]["id"] == alice["user"]["id"]
        assert message["artifact"]["file_name"] == "pic.png"
        assert message["reply_to"]["text"] == "quote me"
        assert message["reactions"] == []
