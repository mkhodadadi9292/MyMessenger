import asyncio
import json

import httpx
import pytest

from tests.helpers import auth_headers, register_user

API = "/api/v1"


@pytest.fixture
def settings(settings):
    # keepalive comments every second so tests can assert "nothing but keepalive"
    settings.sse_keepalive_seconds = 1
    return settings


async def _register(client: httpx.AsyncClient, otp_sender, name: str) -> dict:
    return await register_user(
        client, otp_sender, f"{name}@example.com", name, name.capitalize()
    )


async def _open_chat(client: httpx.AsyncClient, alice: dict, bob: dict) -> int:
    response = await client.post(
        f"{API}/chats/private",
        json={"user_id": alice["user"]["id"]},
        headers=auth_headers(bob["access_token"]),
    )
    assert response.status_code == 200
    return response.json()["id"]


async def _stream_frames(client: httpx.AsyncClient, token: str):
    """Yield parsed SSE frames: ("event", data_dict), ("retry", ms) or ("comment", text).

    The generator is lazy: the HTTP stream opens on the first anext(), so tests
    must consume the initial retry frame BEFORE triggering the event source.
    """
    async with client.stream(
        "GET", f"{API}/notifications/stream", params={"token": token}
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        event_name = None
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data = json.loads(line.split(":", 1)[1].strip())
                yield event_name, data
            elif line.startswith("retry:"):
                yield "retry", line.split(":", 1)[1].strip()
            elif line.startswith(":"):
                yield "comment", line


async def _open_stream(client: httpx.AsyncClient, token: str):
    """Start the stream and wait for the initial retry frame (connection is live)."""
    frames = _stream_frames(client, token)
    assert (await anext(frames))[0] == "retry"
    return frames


async def _recv_notification(frames, timeout: float = 5.0):
    async with asyncio.timeout(timeout):
        async for name, data in frames:
            if name == "notification.new":
                return data
    raise AssertionError("no notification.new frame received")


async def test_sse_stream_requires_token(live_client: httpx.AsyncClient) -> None:
    response = await live_client.get(f"{API}/notifications/stream")
    assert response.status_code == 401

    response = await live_client.get(
        f"{API}/notifications/stream", params={"token": "not-a-token"}
    )
    assert response.status_code == 401


async def test_sse_delivers_notification_on_message(live_server: str, otp_sender) -> None:
    async with httpx.AsyncClient(base_url=live_server) as client:
        alice = await _register(client, otp_sender, "ssealice")
        bob = await _register(client, otp_sender, "ssebob")
        chat_id = await _open_chat(client, alice, bob)

        frames = await _open_stream(client, alice["access_token"])

        response = await client.post(
            f"{API}/chats/{chat_id}/messages",
            json={"text": "hello over sse"},
            headers=auth_headers(bob["access_token"]),
        )
        assert response.status_code == 200

        event = await _recv_notification(frames)
        notification = event["notification"]
        assert event["unread_count"] == 1
        assert notification["type"] == "message"
        assert notification["chat_id"] == chat_id
        assert notification["sender_username"] == "ssebob"
        assert notification["preview"] == "hello over sse"
        assert notification["is_read"] is False

        # the row is persisted and can be listed + marked read via REST
        listed = await client.get(
            f"{API}/notifications", headers=auth_headers(alice["access_token"])
        )
        assert [n["preview"] for n in listed.json()] == ["hello over sse"]
        marked = await client.post(
            f"{API}/notifications/read",
            json={"chat_id": chat_id},
            headers=auth_headers(alice["access_token"]),
        )
        assert marked.json()["unread_count"] == 0


async def test_sse_sender_gets_no_self_notification(live_server: str, otp_sender) -> None:
    async with httpx.AsyncClient(base_url=live_server) as client:
        alice = await _register(client, otp_sender, "ssealice2")
        bob = await _register(client, otp_sender, "ssebob2")
        chat_id = await _open_chat(client, alice, bob)

        frames = await _open_stream(client, alice["access_token"])

        response = await client.post(
            f"{API}/chats/{chat_id}/messages",
            json={"text": "self send"},
            headers=auth_headers(alice["access_token"]),
        )
        assert response.status_code == 200

        saw_comment = False
        async with asyncio.timeout(5):
            async for name, data in frames:
                if name == "notification.new":
                    raise AssertionError(f"sender got a self-notification: {data}")
                if name == "comment":
                    saw_comment = True
                    break
        assert saw_comment, "expected at least one keepalive comment"


async def test_sse_invite_notification(live_server: str, otp_sender) -> None:
    async with httpx.AsyncClient(base_url=live_server) as client:
        alice = await _register(client, otp_sender, "ssealice3")
        bob = await _register(client, otp_sender, "ssebob3")

        group = await client.post(
            f"{API}/chats/groups",
            json={"title": "SSE Team", "is_public": False},
            headers=auth_headers(alice["access_token"]),
        )
        assert group.status_code == 200
        chat_id = group.json()["id"]

        frames = await _open_stream(client, bob["access_token"])

        invited = await client.post(
            f"{API}/chats/{chat_id}/invites",
            json={"user_id": bob["user"]["id"]},
            headers=auth_headers(alice["access_token"]),
        )
        assert invited.status_code == 200

        event = await _recv_notification(frames)
        notification = event["notification"]
        assert notification["type"] == "invite"
        assert notification["invite_id"] == invited.json()["invite_id"]
        assert notification["preview"] == "invited you to SSE Team"
        assert notification["sender_username"] == "ssealice3"
