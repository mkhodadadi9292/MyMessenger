from httpx import AsyncClient

from tests.helpers import auth_headers, register_user

API = "/api/v1"


async def test_private_chat_journey(live_client: AsyncClient, otp_sender) -> None:
    client = live_client
    alice = await register_user(client, otp_sender, "alice@example.com", "alice", "Alice")
    bob = await register_user(client, otp_sender, "bob@example.com", "bob", "Bob")

    added = await client.post(
        f"{API}/contacts",
        json={"identifier": "alice"},
        headers=auth_headers(bob["access_token"]),
    )
    assert added.status_code == 200

    chat = await client.post(
        f"{API}/chats/private",
        json={"user_id": alice["user"]["id"]},
        headers=auth_headers(bob["access_token"]),
    )
    assert chat.status_code == 200
    chat_id = chat.json()["id"]

    first = await client.post(
        f"{API}/chats/{chat_id}/messages",
        json={"text": "hi alice"},
        headers=auth_headers(bob["access_token"]),
    )
    assert first.status_code == 200
    reply = await client.post(
        f"{API}/chats/{chat_id}/messages",
        json={"text": "hi bob", "reply_to_id": first.json()["id"]},
        headers=auth_headers(alice["access_token"]),
    )
    assert reply.status_code == 200
    assert reply.json()["reply_to_id"] == first.json()["id"]

    history = await client.get(
        f"{API}/chats/{chat_id}/messages", headers=auth_headers(alice["access_token"])
    )
    assert [m["text"] for m in history.json()] == ["hi bob", "hi alice"]

    edited = await client.patch(
        f"{API}/messages/{reply.json()['id']}",
        json={"text": "hi bob!"},
        headers=auth_headers(alice["access_token"]),
    )
    assert edited.status_code == 200
    assert edited.json()["text"] == "hi bob!"

    deleted = await client.delete(
        f"{API}/messages/{first.json()['id']}", headers=auth_headers(bob["access_token"])
    )
    assert deleted.status_code == 200
    history = await client.get(
        f"{API}/chats/{chat_id}/messages", headers=auth_headers(alice["access_token"])
    )
    doomed = next(m for m in history.json() if m["id"] == first.json()["id"])
    assert doomed["deleted_at"] is not None
