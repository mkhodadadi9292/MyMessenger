import asyncio

import httpx
import pytest
import websockets

from tests.helpers import auth_headers, register_user

WS_PATH = "/ws"


async def _recv_until(ws, event_type: str, timeout: float = 5.0) -> dict:
    async with asyncio.timeout(timeout):
        while True:
            event = await ws.recv()
            import json

            payload = json.loads(event)
            if payload.get("type") == event_type:
                return payload


async def _register(client: httpx.AsyncClient, otp_sender, name: str) -> dict:
    return await register_user(
        client, otp_sender, f"{name}@example.com", name, name.capitalize()
    )


async def _open_chat(client: httpx.AsyncClient, alice: dict, bob: dict) -> int:
    response = await client.post(
        "/api/v1/chats/private",
        json={"user_id": alice["user"]["id"]},
        headers=auth_headers(bob["access_token"]),
    )
    assert response.status_code == 200
    return response.json()["id"]


def _ws_url(live_server: str, token: str) -> str:
    return live_server.replace("http://", "ws://") + f"{WS_PATH}?token={token}"


async def test_ws_rejects_missing_token(live_server: str) -> None:
    url = live_server.replace("http://", "ws://") + WS_PATH
    with pytest.raises(websockets.exceptions.InvalidStatus) as exc_info:
        async with websockets.connect(url):
            pass
    assert exc_info.value.response.status_code in (403, 4401)


async def test_ws_delivers_messages_and_chat_updates(
    live_server: str, otp_sender
) -> None:
    async with httpx.AsyncClient(base_url=live_server) as client:
        alice = await _register(client, otp_sender, "wsalice")
        bob = await _register(client, otp_sender, "wsbob")
        chat_id = await _open_chat(client, alice, bob)

        async with websockets.connect(
            _ws_url(live_server, alice["access_token"])
        ) as alice_ws, websockets.connect(
            _ws_url(live_server, bob["access_token"])
        ) as bob_ws:
            for ws in (alice_ws, bob_ws):
                await ws.send(
                    '{"type": "subscribe", "chat_id": %d}' % chat_id
                )
                await ws.send('{"type": "ping"}')
                pong = await _recv_until(ws, "pong")
                assert pong["type"] == "pong"

            # REST send reaches both subscribers
            response = await client.post(
                f"/api/v1/chats/{chat_id}/messages",
                json={"text": "hello over ws"},
                headers=auth_headers(alice["access_token"]),
            )
            assert response.status_code == 200

            for ws in (alice_ws, bob_ws):
                event = await _recv_until(ws, "message.new")
                assert event["message"]["text"] == "hello over ws"
                assert event["message"]["sender"]["username"] == "wsalice"
                list_event = await _recv_until(ws, "chat.list_changed")
                assert list_event["type"] == "chat.list_changed"


async def test_ws_send_persists_and_broadcasts(live_server: str, otp_sender) -> None:
    async with httpx.AsyncClient(base_url=live_server) as client:
        alice = await _register(client, otp_sender, "wsalice2")
        bob = await _register(client, otp_sender, "wsbob2")
        chat_id = await _open_chat(client, alice, bob)

        async with websockets.connect(
            _ws_url(live_server, bob["access_token"])
        ) as bob_ws:
            await bob_ws.send('{"type": "subscribe", "chat_id": %d}' % chat_id)
            await bob_ws.send(
                '{"type": "message.send", "chat_id": %d, "text": "sent via ws"}'
                % chat_id
            )
            event = await _recv_until(bob_ws, "message.new")
            assert event["message"]["text"] == "sent via ws"

        history = await client.get(
            f"/api/v1/chats/{chat_id}/messages", headers=auth_headers(alice["access_token"])
        )
        texts = [m["text"] for m in history.json()]
        assert texts == ["sent via ws"]


async def test_ws_send_reply_includes_preview(live_server: str, otp_sender) -> None:
    async with httpx.AsyncClient(base_url=live_server) as client:
        alice = await _register(client, otp_sender, "wsalice3")
        bob = await _register(client, otp_sender, "wsbob3")
        chat_id = await _open_chat(client, alice, bob)
        first = await client.post(
            f"/api/v1/chats/{chat_id}/messages",
            json={"text": "original"},
            headers=auth_headers(alice["access_token"]),
        )
        first_id = first.json()["id"]

        async with websockets.connect(
            _ws_url(live_server, bob["access_token"])
        ) as bob_ws:
            await bob_ws.send('{"type": "subscribe", "chat_id": %d}' % chat_id)
            await bob_ws.send(
                '{"type": "message.send", "chat_id": %d, "text": "replying", "reply_to_id": %d}'
                % (chat_id, first_id)
            )
            event = await _recv_until(bob_ws, "message.new")
            assert event["message"]["reply_to"]["text"] == "original"
            assert event["message"]["reply_to"]["sender_username"] == "wsalice3"


async def test_ws_send_blocked_pair_gets_error(live_server: str, otp_sender) -> None:
    async with httpx.AsyncClient(base_url=live_server) as client:
        alice = await _register(client, otp_sender, "wsalice4")
        bob = await _register(client, otp_sender, "wsbob4")
        chat_id = await _open_chat(client, alice, bob)
        await client.post(
            f"/api/v1/blocked/{bob['user']['id']}",
            headers=auth_headers(alice["access_token"]),
        )

        async with websockets.connect(
            _ws_url(live_server, bob["access_token"])
        ) as bob_ws:
            await bob_ws.send('{"type": "subscribe", "chat_id": %d}' % chat_id)
            await bob_ws.send(
                '{"type": "message.send", "chat_id": %d, "text": "nope"}' % chat_id
            )
            error = await _recv_until(bob_ws, "error")
            assert "cannot message" in error["detail"]
