from tests.helpers import API_V1, auth_headers

API = API_V1

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 128


async def _open_chat(client, alice: dict, bob: dict) -> int:
    response = await client.post(
        f"{API}/chats/private",
        json={"user_id": alice["user"]["id"]},
        headers=auth_headers(bob["access_token"]),
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


async def _send(client, chat_id: int, sender: dict, text: str) -> dict:
    response = await client.post(
        f"{API}/chats/{chat_id}/messages",
        json={"text": text},
        headers=auth_headers(sender["access_token"]),
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _notifications(client, user: dict, **params) -> list[dict]:
    response = await client.get(
        f"{API}/notifications", params=params, headers=auth_headers(user["access_token"])
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _unread(client, user: dict) -> int:
    response = await client.get(
        f"{API}/notifications/unread-count", headers=auth_headers(user["access_token"])
    )
    assert response.status_code == 200, response.text
    return response.json()["count"]


async def _mark_read(client, user: dict, chat_id: int | None = None) -> dict:
    response = await client.post(
        f"{API}/notifications/read",
        json={"chat_id": chat_id},
        headers=auth_headers(user["access_token"]),
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _create_private_group(client, owner: dict, title: str) -> int:
    response = await client.post(
        f"{API}/chats/groups",
        json={"title": title, "is_public": False},
        headers=auth_headers(owner["access_token"]),
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


async def _invite(client, chat_id: int, admin: dict, invitee_id: int) -> dict:
    response = await client.post(
        f"{API}/chats/{chat_id}/invites",
        json={"user_id": invitee_id},
        headers=auth_headers(admin["access_token"]),
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_message_creates_notification_for_recipient_only(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)

    await _send(client, chat_id, alice, "hello bob")

    bob_items = await _notifications(client, bob)
    assert len(bob_items) == 1
    item = bob_items[0]
    assert item["type"] == "message"
    assert item["chat_id"] == chat_id
    assert item["sender_id"] == alice["user"]["id"]
    assert item["sender_username"] == "alice"
    assert item["preview"] == "hello bob"
    assert item["message_id"] is not None
    assert item["is_read"] is False

    # the sender gets no self-notification
    assert await _notifications(client, alice) == []
    assert await _unread(client, alice) == 0
    assert await _unread(client, bob) == 1


async def test_artifact_message_notification_preview(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)

    response = await client.post(
        f"{API}/chats/{chat_id}/artifacts",
        files={"file": ("pic.png", PNG, "image/png")},
        data={"kind": "image"},
        headers=auth_headers(alice["access_token"]),
    )
    assert response.status_code == 200, response.text

    items = await _notifications(client, bob)
    assert len(items) == 1
    assert items[0]["preview"] == "sent pic.png"
    assert items[0]["type"] == "message"


async def test_invite_creates_notification_for_invitee(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _create_private_group(client, alice, "Team")

    invite = await _invite(client, chat_id, alice, bob["user"]["id"])

    items = await _notifications(client, bob)
    assert len(items) == 1
    item = items[0]
    assert item["type"] == "invite"
    assert item["chat_id"] == chat_id
    assert item["sender_id"] == alice["user"]["id"]
    assert item["invite_id"] == invite["invite_id"]
    assert item["preview"] == "invited you to Team"
    assert await _unread(client, bob) == 1
    # the inviter gets no notification
    assert await _unread(client, alice) == 0


async def test_mark_read_per_chat_and_all(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_a = await _open_chat(client, alice, bob)
    await _send(client, chat_a, alice, "first")
    chat_b = await _create_private_group(client, alice, "Group B")
    await _invite(client, chat_b, alice, bob["user"]["id"])

    assert await _unread(client, bob) == 2

    result = await _mark_read(client, bob, chat_id=chat_a)
    assert result["ok"] is True
    assert result["unread_count"] == 1
    remaining = await _notifications(client, bob)
    assert [n["chat_id"] for n in remaining if not n["is_read"]] == [chat_b]

    result = await _mark_read(client, bob)
    assert result["unread_count"] == 0
    assert await _unread(client, bob) == 0
    for item in await _notifications(client, bob):
        assert item["is_read"] is True


async def test_notifications_paginated_newest_first(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    for i in range(3):
        await _send(client, chat_id, alice, f"msg {i}")

    page = await _notifications(client, bob, limit=2)
    assert [n["preview"] for n in page] == ["msg 2", "msg 1"]
    oldest_id = page[-1]["id"]
    page2 = await _notifications(client, bob, before_id=oldest_id, limit=10)
    assert [n["preview"] for n in page2] == ["msg 0"]


async def test_notification_endpoints_require_auth(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    await _send(client, chat_id, alice, "hi")

    for method, path in [
        ("GET", f"{API}/notifications"),
        ("GET", f"{API}/notifications/unread-count"),
        ("POST", f"{API}/notifications/read"),
        ("GET", f"{API}/notifications/stream"),
    ]:
        response = await client.request(method, path)
        assert response.status_code == 401, f"{method} {path} -> {response.status_code}"

    # a notification list is scoped to the current user: another user sees nothing
    carol = await user_factory(username="carol")
    assert await _notifications(client, carol) == []
