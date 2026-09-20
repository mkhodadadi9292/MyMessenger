from tests.helpers import API_V1, auth_headers

API = API_V1


async def _private_group(client, owner: dict, title: str = "Team") -> dict:
    response = await client.post(
        f"{API}/chats/groups",
        json={"title": title, "is_public": False},
        headers=auth_headers(owner["access_token"]),
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_button_invite_requires_acceptance(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat = await _private_group(client, alice)

    invite = await client.post(
        f"{API}/chats/{chat['id']}/invites",
        json={"user_id": bob["user"]["id"]},
        headers=auth_headers(alice["access_token"]),
    )
    assert invite.status_code == 200
    body = invite.json()
    assert body["status"] == "pending"
    assert "invite_id" in body

    members = await client.get(
        f"{API}/chats/{chat['id']}/members", headers=auth_headers(alice["access_token"])
    )
    assert bob["user"]["id"] not in {m["user_id"] for m in members.json()}

    pending = await client.get(f"{API}/me/invites", headers=auth_headers(bob["access_token"]))
    assert pending.status_code == 200
    assert [i["invite_id"] for i in pending.json()] == [body["invite_id"]]
    assert pending.json()[0]["title"] == "Team"
    assert pending.json()[0]["inviter_name"] == "alice"

    accept = await client.post(
        f"{API}/me/invites/{body['invite_id']}/accept", headers=auth_headers(bob["access_token"])
    )
    assert accept.status_code == 200

    members = await client.get(
        f"{API}/chats/{chat['id']}/members", headers=auth_headers(alice["access_token"])
    )
    assert bob["user"]["id"] in {m["user_id"] for m in members.json()}


async def test_decline_invite(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat = await _private_group(client, alice)
    invite = await client.post(
        f"{API}/chats/{chat['id']}/invites",
        json={"user_id": bob["user"]["id"]},
        headers=auth_headers(alice["access_token"]),
    )
    invite_id = invite.json()["invite_id"]
    decline = await client.post(
        f"{API}/me/invites/{invite_id}/decline", headers=auth_headers(bob["access_token"])
    )
    assert decline.status_code == 200

    members = await client.get(
        f"{API}/chats/{chat['id']}/members", headers=auth_headers(alice["access_token"])
    )
    assert bob["user"]["id"] not in {m["user_id"] for m in members.json()}

    late_accept = await client.post(
        f"{API}/me/invites/{invite_id}/accept", headers=auth_headers(bob["access_token"])
    )
    assert late_accept.status_code == 400


async def test_invite_by_non_admin_403(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    carol = await user_factory(username="carol")
    chat = await _private_group(client, alice)
    await client.post(
        f"{API}/chats/{chat['id']}/invites",
        json={"user_id": bob["user"]["id"]},
        headers=auth_headers(alice["access_token"]),
    )
    invite_id = (
        await client.get(f"{API}/me/invites", headers=auth_headers(bob["access_token"]))
    ).json()[0]["invite_id"]
    await client.post(
        f"{API}/me/invites/{invite_id}/accept", headers=auth_headers(bob["access_token"])
    )
    response = await client.post(
        f"{API}/chats/{chat['id']}/invites",
        json={"user_id": carol["user"]["id"]},
        headers=auth_headers(bob["access_token"]),
    )
    assert response.status_code == 403


async def test_invite_already_member_409(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat = await _private_group(client, alice)
    invite = await client.post(
        f"{API}/chats/{chat['id']}/invites",
        json={"user_id": bob["user"]["id"]},
        headers=auth_headers(alice["access_token"]),
    )
    invite_id = invite.json()["invite_id"]
    await client.post(
        f"{API}/me/invites/{invite_id}/accept", headers=auth_headers(bob["access_token"])
    )
    again = await client.post(
        f"{API}/chats/{chat['id']}/invites",
        json={"user_id": bob["user"]["id"]},
        headers=auth_headers(alice["access_token"]),
    )
    assert again.status_code == 409


async def test_invite_already_pending_409(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat = await _private_group(client, alice)
    headers = auth_headers(alice["access_token"])
    first = await client.post(
        f"{API}/chats/{chat['id']}/invites", json={"user_id": bob["user"]["id"]}, headers=headers
    )
    assert first.status_code == 200
    second = await client.post(
        f"{API}/chats/{chat['id']}/invites", json={"user_id": bob["user"]["id"]}, headers=headers
    )
    assert second.status_code == 409


async def test_invite_public_group_400(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    response = await client.post(
        f"{API}/chats/groups",
        json={"title": "Public", "is_public": True},
        headers=auth_headers(alice["access_token"]),
    )
    chat_id = response.json()["id"]
    invite = await client.post(
        f"{API}/chats/{chat_id}/invites",
        json={"user_id": bob["user"]["id"]},
        headers=auth_headers(alice["access_token"]),
    )
    assert invite.status_code == 400


async def test_invite_link_flow(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat = await _private_group(client, alice)

    link = await client.post(
        f"{API}/chats/{chat['id']}/invite-links", headers=auth_headers(alice["access_token"])
    )
    assert link.status_code == 200
    body = link.json()
    assert body["token"]
    assert body["url"].endswith(f"/invites/{body['token']}")
    assert body["expires_at"]

    info = await client.get(f"{API}/invites/{body['token']}", headers=auth_headers(bob["access_token"]))
    assert info.status_code == 200
    assert info.json()["chat_id"] == chat["id"]
    assert info.json()["title"] == "Team"
    assert info.json()["inviter_name"] == "alice"

    accept = await client.post(
        f"{API}/invites/{body['token']}/accept", headers=auth_headers(bob["access_token"])
    )
    assert accept.status_code == 200
    members = await client.get(
        f"{API}/chats/{chat['id']}/members", headers=auth_headers(alice["access_token"])
    )
    assert bob["user"]["id"] in {m["user_id"] for m in members.json()}


async def test_invite_link_invalid_token_404(client, user_factory) -> None:
    tokens = await user_factory()
    response = await client.get(
        f"{API}/invites/does-not-exist", headers=auth_headers(tokens["access_token"])
    )
    assert response.status_code == 404


async def test_invite_link_accept_twice_409(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat = await _private_group(client, alice)
    link = await client.post(
        f"{API}/chats/{chat['id']}/invite-links", headers=auth_headers(alice["access_token"])
    )
    token = link.json()["token"]
    headers = auth_headers(bob["access_token"])
    assert (await client.post(f"{API}/invites/{token}/accept", headers=headers)).status_code == 200
    second = await client.post(f"{API}/invites/{token}/accept", headers=headers)
    assert second.status_code == 409


async def test_invite_link_expired_400(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat = await _private_group(client, alice)
    link = await client.post(
        f"{API}/chats/{chat['id']}/invite-links",
        json={"ttl_seconds": 0},
        headers=auth_headers(alice["access_token"]),
    )
    token = link.json()["token"]
    accept = await client.post(
        f"{API}/invites/{token}/accept", headers=auth_headers(bob["access_token"])
    )
    assert accept.status_code == 400


async def test_invite_link_for_public_group_400(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    response = await client.post(
        f"{API}/chats/groups",
        json={"title": "Public", "is_public": True},
        headers=auth_headers(alice["access_token"]),
    )
    chat_id = response.json()["id"]
    link = await client.post(
        f"{API}/chats/{chat_id}/invite-links", headers=auth_headers(alice["access_token"])
    )
    assert link.status_code == 400
