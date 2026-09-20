from tests.helpers import API_V1, auth_headers

API = API_V1


async def _open_private_chat(client, user_id: int, headers: dict) -> dict:
    response = await client.post(f"{API}/chats/private", json={"user_id": user_id}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def _create_group(client, headers: dict, title: str, is_public: bool) -> dict:
    response = await client.post(
        f"{API}/chats/groups",
        json={"title": title, "description": "d", "is_public": is_public},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _member_ids(client, chat_id: int, headers: dict) -> set[int]:
    response = await client.get(f"{API}/chats/{chat_id}/members", headers=headers)
    assert response.status_code == 200, response.text
    return {m["user_id"] for m in response.json()}


async def test_chat_list_starts_empty(client, user_factory) -> None:
    tokens = await user_factory()
    response = await client.get(f"{API}/chats", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json() == []


async def test_open_private_chat(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat = await _open_private_chat(
        client, alice["user"]["id"], auth_headers(bob["access_token"])
    )
    assert chat["type"] == "private"
    assert chat["title"] is None
    members = await _member_ids(client, chat["id"], auth_headers(bob["access_token"]))
    assert members == {alice["user"]["id"], bob["user"]["id"]}


async def test_private_chat_created_once(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    bob_headers = auth_headers(bob["access_token"])
    alice_headers = auth_headers(alice["access_token"])
    first = await _open_private_chat(client, alice["user"]["id"], bob_headers)
    second = await _open_private_chat(client, alice["user"]["id"], bob_headers)
    third = await _open_private_chat(client, bob["user"]["id"], alice_headers)
    assert first["id"] == second["id"] == third["id"]


async def test_private_chat_with_self_400(client, user_factory) -> None:
    tokens = await user_factory()
    response = await client.post(
        f"{API}/chats/private",
        json={"user_id": tokens["user"]["id"]},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 400


async def test_private_chat_unknown_user_404(client, user_factory) -> None:
    tokens = await user_factory()
    response = await client.post(
        f"{API}/chats/private",
        json={"user_id": 999999},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404


async def test_create_private_group(client, user_factory) -> None:
    tokens = await user_factory(username="alice")
    chat = await _create_group(client, auth_headers(tokens["access_token"]), "Team", False)
    assert chat["type"] == "group"
    assert chat["is_public"] is False
    assert chat["owner_id"] == tokens["user"]["id"]
    members = await _member_ids(client, chat["id"], auth_headers(tokens["access_token"]))
    assert members == {tokens["user"]["id"]}


async def test_create_public_group(client, user_factory) -> None:
    tokens = await user_factory()
    chat = await _create_group(client, auth_headers(tokens["access_token"]), "Public", True)
    assert chat["is_public"] is True


async def test_create_group_missing_title_422(client, user_factory) -> None:
    tokens = await user_factory()
    response = await client.post(
        f"{API}/chats/groups",
        json={"is_public": False},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 422


async def test_get_chat_members_only(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat = await _create_group(client, auth_headers(alice["access_token"]), "Team", False)
    response = await client.get(f"{API}/chats/{chat['id']}", headers=auth_headers(bob["access_token"]))
    assert response.status_code == 403


async def test_update_chat_admin_only(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat = await _create_group(client, auth_headers(alice["access_token"]), "Team", True)
    await client.post(f"{API}/chats/{chat['id']}/join", headers=auth_headers(bob["access_token"]))

    by_member = await client.patch(
        f"{API}/chats/{chat['id']}",
        json={"title": "Hacked"},
        headers=auth_headers(bob["access_token"]),
    )
    assert by_member.status_code == 403

    by_owner = await client.patch(
        f"{API}/chats/{chat['id']}",
        json={"title": "Renamed"},
        headers=auth_headers(alice["access_token"]),
    )
    assert by_owner.status_code == 200
    assert by_owner.json()["title"] == "Renamed"


async def test_admin_adds_member_private_group_creates_invite(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat = await _create_group(client, auth_headers(alice["access_token"]), "Team", False)
    response = await client.post(
        f"{API}/chats/{chat['id']}/members",
        json={"user_id": bob["user"]["id"]},
        headers=auth_headers(alice["access_token"]),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert "invite_id" in body
    members = await _member_ids(client, chat["id"], auth_headers(alice["access_token"]))
    assert bob["user"]["id"] not in members


async def test_member_cannot_invite_private_group(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat = await _create_group(client, auth_headers(alice["access_token"]), "Team", True)
    await client.post(f"{API}/chats/{chat['id']}/join", headers=auth_headers(bob["access_token"]))
    response = await client.post(
        f"{API}/chats/{chat['id']}/members",
        json={"user_id": 999999},
        headers=auth_headers(bob["access_token"]),
    )
    assert response.status_code == 403


async def test_admin_adds_member_public_group_directly(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat = await _create_group(client, auth_headers(alice["access_token"]), "Public", True)
    response = await client.post(
        f"{API}/chats/{chat['id']}/members",
        json={"user_id": bob["user"]["id"]},
        headers=auth_headers(alice["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["user_id"] == bob["user"]["id"]
    members = await _member_ids(client, chat["id"], auth_headers(alice["access_token"]))
    assert bob["user"]["id"] in members


async def test_admin_removes_member(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat = await _create_group(client, auth_headers(alice["access_token"]), "Public", True)
    await client.post(f"{API}/chats/{chat['id']}/join", headers=auth_headers(bob["access_token"]))
    response = await client.delete(
        f"{API}/chats/{chat['id']}/members/{bob['user']['id']}",
        headers=auth_headers(alice["access_token"]),
    )
    assert response.status_code == 200
    members = await _member_ids(client, chat["id"], auth_headers(alice["access_token"]))
    assert bob["user"]["id"] not in members


async def test_admin_cannot_remove_admin(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    carol = await user_factory(username="carol")
    chat = await _create_group(client, auth_headers(alice["access_token"]), "Public", True)
    alice_headers = auth_headers(alice["access_token"])
    await client.post(f"{API}/chats/{chat['id']}/join", headers=auth_headers(bob["access_token"]))
    await client.post(f"{API}/chats/{chat['id']}/join", headers=auth_headers(carol["access_token"]))
    await client.post(f"{API}/chats/{chat['id']}/admins/{bob['user']['id']}", headers=alice_headers)
    await client.post(f"{API}/chats/{chat['id']}/admins/{carol['user']['id']}", headers=alice_headers)

    response = await client.delete(
        f"{API}/chats/{chat['id']}/members/{carol['user']['id']}",
        headers=auth_headers(bob["access_token"]),
    )
    assert response.status_code == 403


async def test_owner_cannot_be_removed(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat = await _create_group(client, auth_headers(alice["access_token"]), "Public", True)
    await client.post(f"{API}/chats/{chat['id']}/join", headers=auth_headers(bob["access_token"]))
    response = await client.delete(
        f"{API}/chats/{chat['id']}/members/{alice['user']['id']}",
        headers=auth_headers(bob["access_token"]),
    )
    assert response.status_code == 403


async def test_join_public_group(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat = await _create_group(client, auth_headers(alice["access_token"]), "Public", True)
    response = await client.post(f"{API}/chats/{chat['id']}/join", headers=auth_headers(bob["access_token"]))
    assert response.status_code == 200
    members = await _member_ids(client, chat["id"], auth_headers(alice["access_token"]))
    assert bob["user"]["id"] in members


async def test_join_public_group_twice_409(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat = await _create_group(client, auth_headers(alice["access_token"]), "Public", True)
    headers = auth_headers(bob["access_token"])
    assert (await client.post(f"{API}/chats/{chat['id']}/join", headers=headers)).status_code == 200
    second = await client.post(f"{API}/chats/{chat['id']}/join", headers=headers)
    assert second.status_code == 409


async def test_join_private_group_forbidden(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat = await _create_group(client, auth_headers(alice["access_token"]), "Team", False)
    response = await client.post(f"{API}/chats/{chat['id']}/join", headers=auth_headers(bob["access_token"]))
    assert response.status_code == 403


async def test_leave_group(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat = await _create_group(client, auth_headers(alice["access_token"]), "Public", True)
    await client.post(f"{API}/chats/{chat['id']}/join", headers=auth_headers(bob["access_token"]))
    response = await client.delete(f"{API}/chats/{chat['id']}/leave", headers=auth_headers(bob["access_token"]))
    assert response.status_code == 200
    members = await _member_ids(client, chat["id"], auth_headers(alice["access_token"]))
    assert bob["user"]["id"] not in members


async def test_leave_private_chat_400(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat = await _open_private_chat(client, alice["user"]["id"], auth_headers(bob["access_token"]))
    response = await client.delete(
        f"{API}/chats/{chat['id']}/leave", headers=auth_headers(bob["access_token"])
    )
    assert response.status_code == 400


async def test_last_member_leaving_deletes_group(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    chat = await _create_group(client, auth_headers(alice["access_token"]), "Team", False)
    response = await client.delete(
        f"{API}/chats/{chat['id']}/leave", headers=auth_headers(alice["access_token"])
    )
    assert response.status_code == 200
    gone = await client.get(f"{API}/chats/{chat['id']}", headers=auth_headers(alice["access_token"]))
    assert gone.status_code == 404


async def test_owner_leaving_transfers_ownership(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat = await _create_group(client, auth_headers(alice["access_token"]), "Public", True)
    await client.post(f"{API}/chats/{chat['id']}/join", headers=auth_headers(bob["access_token"]))
    response = await client.delete(
        f"{API}/chats/{chat['id']}/leave", headers=auth_headers(alice["access_token"])
    )
    assert response.status_code == 200
    chat_info = await client.get(f"{API}/chats/{chat['id']}", headers=auth_headers(bob["access_token"]))
    assert chat_info.json()["owner_id"] == bob["user"]["id"]


async def test_promote_to_admin(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat = await _create_group(client, auth_headers(alice["access_token"]), "Public", True)
    await client.post(f"{API}/chats/{chat['id']}/join", headers=auth_headers(bob["access_token"]))
    response = await client.post(
        f"{API}/chats/{chat['id']}/admins/{bob['user']['id']}",
        headers=auth_headers(alice["access_token"]),
    )
    assert response.status_code == 200
    members = await client.get(f"{API}/chats/{chat['id']}/members", headers=auth_headers(alice["access_token"]))
    roles = {m["user_id"]: m["role"] for m in members.json()}
    assert roles[bob["user"]["id"]] == "admin"
    assert roles[alice["user"]["id"]] == "owner"


async def test_promote_requires_owner(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    carol = await user_factory(username="carol")
    chat = await _create_group(client, auth_headers(alice["access_token"]), "Public", True)
    await client.post(f"{API}/chats/{chat['id']}/join", headers=auth_headers(bob["access_token"]))
    await client.post(f"{API}/chats/{chat['id']}/join", headers=auth_headers(carol["access_token"]))
    response = await client.post(
        f"{API}/chats/{chat['id']}/admins/{carol['user']['id']}",
        headers=auth_headers(bob["access_token"]),
    )
    assert response.status_code == 403
