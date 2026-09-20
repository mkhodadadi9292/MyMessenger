from httpx import AsyncClient

from tests.helpers import auth_headers, register_user

API = "/api/v1"


async def test_blocking_journey(live_client: AsyncClient, otp_sender) -> None:
    client = live_client
    alice = await register_user(client, otp_sender, "alice@example.com", "alice", "Alice")
    bob = await register_user(client, otp_sender, "bob@example.com", "bob", "Bob")

    chat = await client.post(
        f"{API}/chats/private",
        json={"user_id": alice["user"]["id"]},
        headers=auth_headers(bob["access_token"]),
    )
    chat_id = chat.json()["id"]

    blocked = await client.post(
        f"{API}/blocked/{bob['user']['id']}", headers=auth_headers(alice["access_token"])
    )
    assert blocked.status_code == 200

    message = await client.post(
        f"{API}/chats/{chat_id}/messages",
        json={"text": "are you there?"},
        headers=auth_headers(bob["access_token"]),
    )
    assert message.status_code == 403

    profile = await client.get(
        f"{API}/users/{alice['user']['id']}", headers=auth_headers(bob["access_token"])
    )
    assert profile.status_code == 403

    unblocked = await client.delete(
        f"{API}/blocked/{bob['user']['id']}", headers=auth_headers(alice["access_token"])
    )
    assert unblocked.status_code == 200

    message = await client.post(
        f"{API}/chats/{chat_id}/messages",
        json={"text": "are you there?"},
        headers=auth_headers(bob["access_token"]),
    )
    assert message.status_code == 200

    profile = await client.get(
        f"{API}/users/{alice['user']['id']}", headers=auth_headers(bob["access_token"])
    )
    assert profile.status_code == 200
