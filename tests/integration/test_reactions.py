from tests.helpers import API_V1, auth_headers

API = API_V1


async def _setup(client, user_factory) -> tuple[dict, dict, int, int]:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat = await client.post(
        f"{API}/chats/private",
        json={"user_id": alice["user"]["id"]},
        headers=auth_headers(bob["access_token"]),
    )
    chat_id = chat.json()["id"]
    sent = await client.post(
        f"{API}/chats/{chat_id}/messages",
        json={"text": "react to me"},
        headers=auth_headers(alice["access_token"]),
    )
    return alice, bob, chat_id, sent.json()["id"]


async def _react(client, user: dict, message_id: int, code: str):
    return await client.put(
        f"{API}/messages/{message_id}/reaction",
        json={"code": code},
        headers=auth_headers(user["access_token"]),
    )


async def _reactions_in_history(client, user: dict, chat_id: int, message_id: int) -> list[dict]:
    history = await client.get(
        f"{API}/chats/{chat_id}/messages", headers=auth_headers(user["access_token"])
    )
    return next(m for m in history.json() if m["id"] == message_id)["reactions"]


async def test_react_and_see_in_history(client, user_factory) -> None:
    alice, bob, chat_id, message_id = await _setup(client, user_factory)
    response = await _react(client, bob, message_id, "heart")
    assert response.status_code == 200
    assert response.json()["reactions"] == [
        {"code": "heart", "count": 1, "user_ids": [bob["user"]["id"]]}
    ]
    assert await _reactions_in_history(client, alice, chat_id, message_id) == [
        {"code": "heart", "count": 1, "user_ids": [bob["user"]["id"]]}
    ]


async def test_reactions_grouped_by_code(client, user_factory) -> None:
    alice, bob, chat_id, message_id = await _setup(client, user_factory)
    await _react(client, alice, message_id, "like")
    await _react(client, bob, message_id, "like")
    reactions = await _reactions_in_history(client, alice, chat_id, message_id)
    assert reactions[0]["code"] == "like"
    assert reactions[0]["count"] == 2


async def test_new_reaction_replaces_previous(client, user_factory) -> None:
    _, bob, chat_id, message_id = await _setup(client, user_factory)
    await _react(client, bob, message_id, "like")
    await _react(client, bob, message_id, "fire")
    reactions = await _reactions_in_history(client, bob, chat_id, message_id)
    assert [r["code"] for r in reactions] == ["fire"]


async def test_remove_reaction(client, user_factory) -> None:
    _, bob, chat_id, message_id = await _setup(client, user_factory)
    await _react(client, bob, message_id, "like")
    response = await client.delete(
        f"{API}/messages/{message_id}/reaction", headers=auth_headers(bob["access_token"])
    )
    assert response.status_code == 200
    assert response.json()["reactions"] == []
    assert await _reactions_in_history(client, bob, chat_id, message_id) == []


async def test_unknown_code_400(client, user_factory) -> None:
    _, bob, _, message_id = await _setup(client, user_factory)
    assert (await _react(client, bob, message_id, "poop")).status_code == 400


async def test_unknown_message_404(client, user_factory) -> None:
    _, bob, _, _ = await _setup(client, user_factory)
    assert (await _react(client, bob, 999999, "like")).status_code == 404


async def test_non_member_403(client, user_factory) -> None:
    _, _, _, message_id = await _setup(client, user_factory)
    carol = await user_factory(username="carol")
    assert (await _react(client, carol, message_id, "like")).status_code == 403


async def test_blocked_pair_cannot_react(client, user_factory) -> None:
    alice, bob, _, message_id = await _setup(client, user_factory)
    await client.post(
        f"{API}/blocked/{bob['user']['id']}", headers=auth_headers(alice["access_token"])
    )
    assert (await _react(client, bob, message_id, "like")).status_code == 403


async def test_cannot_react_to_deleted_message(client, user_factory) -> None:
    alice, bob, _, message_id = await _setup(client, user_factory)
    await client.delete(
        f"{API}/messages/{message_id}", headers=auth_headers(alice["access_token"])
    )
    assert (await _react(client, bob, message_id, "like")).status_code == 400