from tests.helpers import API_V1, auth_headers

API = API_V1


async def _open_chat(client, alice: dict, bob: dict) -> int:
    response = await client.post(
        f"{API}/chats/private",
        json={"user_id": alice["user"]["id"]},
        headers=auth_headers(bob["access_token"]),
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


async def _send(client, chat_id: int, sender: dict, text: str, reply_to_id: int | None = None) -> dict:
    response = await client.post(
        f"{API}/chats/{chat_id}/messages",
        json={"text": text, "reply_to_id": reply_to_id},
        headers=auth_headers(sender["access_token"]),
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _history(client, chat_id: int, reader: dict, **params) -> list[dict]:
    response = await client.get(
        f"{API}/chats/{chat_id}/messages",
        params=params,
        headers=auth_headers(reader["access_token"]),
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_send_and_list_messages(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)

    sent = await _send(client, chat_id, alice, "hello bob")
    assert sent["text"] == "hello bob"
    assert sent["sender"]["id"] == alice["user"]["id"]
    assert sent["reply_to_id"] is None
    assert sent["artifact"] is None

    history = await _history(client, chat_id, bob)
    assert [m["text"] for m in history] == ["hello bob"]


async def test_empty_message_rejected(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    response = await client.post(
        f"{API}/chats/{chat_id}/messages",
        json={"text": ""},
        headers=auth_headers(alice["access_token"]),
    )
    assert response.status_code == 400
    response = await client.post(
        f"{API}/chats/{chat_id}/messages",
        json={},
        headers=auth_headers(alice["access_token"]),
    )
    assert response.status_code == 400


async def test_non_member_cannot_send_or_read(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    carol = await user_factory(username="carol")
    chat_id = await _open_chat(client, alice, bob)

    send = await client.post(
        f"{API}/chats/{chat_id}/messages",
        json={"text": "intruder"},
        headers=auth_headers(carol["access_token"]),
    )
    assert send.status_code == 403

    read = await client.get(
        f"{API}/chats/{chat_id}/messages", headers=auth_headers(carol["access_token"])
    )
    assert read.status_code == 403


async def test_reply_flow(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)

    first = await _send(client, chat_id, alice, "first")
    second = await _send(client, chat_id, bob, "second", reply_to_id=first["id"])
    assert second["reply_to_id"] == first["id"]

    history = await _history(client, chat_id, alice)
    assert [(m["text"], m["reply_to_id"]) for m in history] == [
        ("second", first["id"]),
        ("first", None),
    ]


async def test_reply_to_message_in_other_chat_400(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    carol = await user_factory(username="carol")
    chat_ab = await _open_chat(client, alice, bob)
    chat_bc = await _open_chat(client, bob, carol)

    foreign = await _send(client, chat_ab, alice, "in other chat")
    response = await client.post(
        f"{API}/chats/{chat_bc}/messages",
        json={"text": "bad reply", "reply_to_id": foreign["id"]},
        headers=auth_headers(bob["access_token"]),
    )
    assert response.status_code == 400


async def test_reply_to_unknown_message_404(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    response = await client.post(
        f"{API}/chats/{chat_id}/messages",
        json={"text": "ghost reply", "reply_to_id": 999999},
        headers=auth_headers(alice["access_token"]),
    )
    assert response.status_code == 404


async def test_reply_to_deleted_message_allowed(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    first = await _send(client, chat_id, alice, "will be deleted")
    await client.delete(
        f"{API}/messages/{first['id']}", headers=auth_headers(alice["access_token"])
    )
    reply = await _send(client, chat_id, bob, "replying anyway", reply_to_id=first["id"])
    assert reply["reply_to_id"] == first["id"]


async def test_pagination(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    for i in range(1, 6):
        await _send(client, chat_id, alice, f"m{i}")

    page1 = await _history(client, chat_id, bob, limit=2)
    assert [m["text"] for m in page1] == ["m5", "m4"]
    page2 = await _history(client, chat_id, bob, limit=2, before_id=page1[-1]["id"])
    assert [m["text"] for m in page2] == ["m3", "m2"]
    page3 = await _history(client, chat_id, bob, limit=2, before_id=page2[-1]["id"])
    assert [m["text"] for m in page3] == ["m1"]


async def test_pagination_limit_out_of_range_400(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    for limit in (0, 150):
        response = await client.get(
            f"{API}/chats/{chat_id}/messages",
            params={"limit": limit},
            headers=auth_headers(bob["access_token"]),
        )
        assert response.status_code == 400


async def test_before_id_from_other_chat_400(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    carol = await user_factory(username="carol")
    chat_ab = await _open_chat(client, alice, bob)
    chat_bc = await _open_chat(client, bob, carol)
    foreign = await _send(client, chat_bc, bob, "other chat")
    response = await client.get(
        f"{API}/chats/{chat_ab}/messages",
        params={"before_id": foreign["id"]},
        headers=auth_headers(alice["access_token"]),
    )
    assert response.status_code == 400


async def test_edit_message(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    sent = await _send(client, chat_id, alice, "original")
    edited = await client.patch(
        f"{API}/messages/{sent['id']}",
        json={"text": "edited"},
        headers=auth_headers(alice["access_token"]),
    )
    assert edited.status_code == 200
    assert edited.json()["text"] == "edited"
    assert edited.json()["edited_at"] is not None


async def test_edit_other_users_message_403(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    sent = await _send(client, chat_id, alice, "mine")
    response = await client.patch(
        f"{API}/messages/{sent['id']}",
        json={"text": "stolen"},
        headers=auth_headers(bob["access_token"]),
    )
    assert response.status_code == 403


async def test_delete_message_soft(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    sent = await _send(client, chat_id, alice, "doomed")
    response = await client.delete(
        f"{API}/messages/{sent['id']}", headers=auth_headers(alice["access_token"])
    )
    assert response.status_code == 200
    history = await _history(client, chat_id, bob)
    deleted = next(m for m in history if m["id"] == sent["id"])
    assert deleted["deleted_at"] is not None
    assert deleted["text"] is None


async def test_delete_other_users_message_403(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    sent = await _send(client, chat_id, alice, "mine")
    response = await client.delete(
        f"{API}/messages/{sent['id']}", headers=auth_headers(bob["access_token"])
    )
    assert response.status_code == 403


async def test_blocked_users_cannot_message_each_other(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    await client.post(
        f"{API}/blocked/{bob['user']['id']}", headers=auth_headers(alice["access_token"])
    )

    from_bob = await client.post(
        f"{API}/chats/{chat_id}/messages",
        json={"text": "let me in"},
        headers=auth_headers(bob["access_token"]),
    )
    assert from_bob.status_code == 403
    from_alice = await client.post(
        f"{API}/chats/{chat_id}/messages",
        json={"text": "nope"},
        headers=auth_headers(alice["access_token"]),
    )
    assert from_alice.status_code == 403

    await client.delete(
        f"{API}/blocked/{bob['user']['id']}", headers=auth_headers(alice["access_token"])
    )
    after_unblock = await client.post(
        f"{API}/chats/{chat_id}/messages",
        json={"text": "ok now"},
        headers=auth_headers(bob["access_token"]),
    )
    assert after_unblock.status_code == 200


async def test_chat_list_contains_last_message(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    await _send(client, chat_id, alice, "latest")
    listing = await client.get(f"{API}/chats", headers=auth_headers(bob["access_token"]))
    assert listing.status_code == 200
    chats = listing.json()
    assert [c["id"] for c in chats] == [chat_id]
    assert chats[0]["last_message"]["text"] == "latest"
