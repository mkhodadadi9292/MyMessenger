from tests.helpers import API_V1, auth_headers

API = API_V1


async def test_blocked_list_starts_empty(client, user_factory) -> None:
    tokens = await user_factory()
    response = await client.get(f"{API}/blocked", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json() == []


async def test_block_and_list(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    headers = auth_headers(bob["access_token"])
    response = await client.post(f"{API}/blocked/{alice['user']['id']}", headers=headers)
    assert response.status_code == 200
    listing = await client.get(f"{API}/blocked", headers=headers)
    assert [u["user_id"] for u in listing.json()] == [alice["user"]["id"]]


async def test_block_duplicate_409(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    headers = auth_headers(bob["access_token"])
    assert (await client.post(f"{API}/blocked/{alice['user']['id']}", headers=headers)).status_code == 200
    second = await client.post(f"{API}/blocked/{alice['user']['id']}", headers=headers)
    assert second.status_code == 409


async def test_block_self_400(client, user_factory) -> None:
    tokens = await user_factory()
    response = await client.post(
        f"{API}/blocked/{tokens['user']['id']}", headers=auth_headers(tokens["access_token"])
    )
    assert response.status_code == 400


async def test_unblock(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    headers = auth_headers(bob["access_token"])
    await client.post(f"{API}/blocked/{alice['user']['id']}", headers=headers)
    response = await client.delete(f"{API}/blocked/{alice['user']['id']}", headers=headers)
    assert response.status_code == 200
    listing = await client.get(f"{API}/blocked", headers=headers)
    assert listing.json() == []


async def test_unblock_non_blocked_404(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    response = await client.delete(
        f"{API}/blocked/{alice['user']['id']}", headers=auth_headers(bob["access_token"])
    )
    assert response.status_code == 404


async def test_blocked_user_cannot_view_profile(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    await client.post(
        f"{API}/blocked/{bob['user']['id']}", headers=auth_headers(alice["access_token"])
    )
    response = await client.get(
        f"{API}/users/{alice['user']['id']}", headers=auth_headers(bob["access_token"])
    )
    assert response.status_code == 403


async def test_blocked_user_cannot_be_added_to_contacts(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    await client.post(
        f"{API}/blocked/{bob['user']['id']}", headers=auth_headers(alice["access_token"])
    )
    response = await client.post(
        f"{API}/contacts",
        json={"identifier": "alice"},
        headers=auth_headers(bob["access_token"]),
    )
    assert response.status_code == 403


async def test_blocked_user_hidden_from_search(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    await client.post(
        f"{API}/blocked/{bob['user']['id']}", headers=auth_headers(alice["access_token"])
    )
    response = await client.get(
        f"{API}/users/search", params={"q": "alice"}, headers=auth_headers(bob["access_token"])
    )
    assert response.status_code == 200
    assert response.json() == []
