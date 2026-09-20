from httpx import AsyncClient

from tests.helpers import auth_headers, register_user

API = "/api/v1"

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 128


async def test_private_group_invite_journey(live_client: AsyncClient, otp_sender) -> None:
    client = live_client
    alice = await register_user(client, otp_sender, "alice@example.com", "alice", "Alice")
    bob = await register_user(client, otp_sender, "bob@example.com", "bob", "Bob")

    group = await client.post(
        f"{API}/chats/groups",
        json={"title": "Team", "is_public": False},
        headers=auth_headers(alice["access_token"]),
    )
    assert group.status_code == 200
    group_id = group.json()["id"]

    invite = await client.post(
        f"{API}/chats/{group_id}/invites",
        json={"user_id": bob["user"]["id"]},
        headers=auth_headers(alice["access_token"]),
    )
    assert invite.status_code == 200
    invite_id = invite.json()["invite_id"]

    pending = await client.get(f"{API}/me/invites", headers=auth_headers(bob["access_token"]))
    assert [i["invite_id"] for i in pending.json()] == [invite_id]
    assert pending.json()[0]["title"] == "Team"

    accepted = await client.post(
        f"{API}/me/invites/{invite_id}/accept", headers=auth_headers(bob["access_token"])
    )
    assert accepted.status_code == 200

    sent = await client.post(
        f"{API}/chats/{group_id}/messages",
        json={"text": "welcome bob"},
        headers=auth_headers(alice["access_token"]),
    )
    assert sent.status_code == 200
    history = await client.get(
        f"{API}/chats/{group_id}/messages", headers=auth_headers(bob["access_token"])
    )
    assert [m["text"] for m in history.json()] == ["welcome bob"]

    promoted = await client.post(
        f"{API}/chats/{group_id}/admins/{bob['user']['id']}",
        headers=auth_headers(alice["access_token"]),
    )
    assert promoted.status_code == 200
    members = await client.get(
        f"{API}/chats/{group_id}/members", headers=auth_headers(alice["access_token"])
    )
    roles = {m["user_id"]: m["role"] for m in members.json()}
    assert roles[bob["user"]["id"]] == "admin"
    assert roles[alice["user"]["id"]] == "owner"


async def test_public_group_artifact_journey(live_client: AsyncClient, otp_sender) -> None:
    client = live_client
    alice = await register_user(client, otp_sender, "alice@example.com", "alice", "Alice")
    bob = await register_user(client, otp_sender, "bob@example.com", "bob", "Bob")

    group = await client.post(
        f"{API}/chats/groups",
        json={"title": "Public", "is_public": True},
        headers=auth_headers(alice["access_token"]),
    )
    group_id = group.json()["id"]

    joined = await client.post(
        f"{API}/chats/{group_id}/join", headers=auth_headers(bob["access_token"])
    )
    assert joined.status_code == 200

    uploaded = await client.post(
        f"{API}/chats/{group_id}/artifacts",
        files={"file": ("pic.png", PNG, "image/png")},
        data={"kind": "image"},
        headers=auth_headers(alice["access_token"]),
    )
    assert uploaded.status_code == 200
    artifact = uploaded.json()["artifact"]

    downloaded = await client.get(
        f"{API}/artifacts/{artifact['id']}/download", headers=auth_headers(bob["access_token"])
    )
    assert downloaded.status_code == 200
    assert downloaded.content == PNG
