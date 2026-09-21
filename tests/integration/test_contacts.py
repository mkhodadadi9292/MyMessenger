from tests.helpers import API_V1, auth_headers

API = API_V1


async def test_contacts_start_empty(client, user_factory) -> None:
    tokens = await user_factory()
    response = await client.get(f"{API}/contacts", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json() == []


async def test_add_contact_by_username(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    response = await client.post(
        f"{API}/contacts",
        json={"identifier": "alice"},
        headers=auth_headers(bob["access_token"]),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == alice["user"]["id"]
    assert body["username"] == "alice"
    assert "phone" not in body

    listing = await client.get(f"{API}/contacts", headers=auth_headers(bob["access_token"]))
    assert [c["user_id"] for c in listing.json()] == [alice["user"]["id"]]


async def test_add_contact_by_phone(client, user_factory) -> None:
    alice = await user_factory(username="alice", identifier="+989123456789")
    bob = await user_factory(username="bob")
    response = await client.post(
        f"{API}/contacts",
        json={"identifier": "+989123456789"},
        headers=auth_headers(bob["access_token"]),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == alice["user"]["id"]
    assert "phone" not in body


async def test_add_contact_duplicate_409(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    headers = auth_headers(bob["access_token"])
    first = await client.post(f"{API}/contacts", json={"identifier": "alice"}, headers=headers)
    assert first.status_code == 200
    second = await client.post(f"{API}/contacts", json={"identifier": "alice"}, headers=headers)
    assert second.status_code == 409


async def test_add_self_400(client, user_factory) -> None:
    tokens = await user_factory(username="alice")
    response = await client.post(
        f"{API}/contacts",
        json={"identifier": "alice"},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 400


async def test_add_unknown_identifier_404(client, user_factory) -> None:
    tokens = await user_factory()
    response = await client.post(
        f"{API}/contacts",
        json={"identifier": "ghost"},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404


async def test_remove_contact(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    headers = auth_headers(bob["access_token"])
    await client.post(f"{API}/contacts", json={"identifier": "alice"}, headers=headers)
    response = await client.delete(f"{API}/contacts/{alice['user']['id']}", headers=headers)
    assert response.status_code == 200
    listing = await client.get(f"{API}/contacts", headers=headers)
    assert listing.json() == []


async def test_remove_non_contact_404(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    response = await client.delete(
        f"{API}/contacts/{alice['user']['id']}", headers=auth_headers(bob["access_token"])
    )
    assert response.status_code == 404


async def test_rename_contact(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    await client.post(
        f"{API}/contacts",
        json={"identifier": "alice"},
        headers=auth_headers(bob["access_token"]),
    )
    response = await client.patch(
        f"{API}/contacts/{alice['user']['id']}",
        json={"name": "My Best Friend"},
        headers=auth_headers(bob["access_token"]),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "My Best Friend"
    assert body["username"] == "alice"

    listing = await client.get(f"{API}/contacts", headers=auth_headers(bob["access_token"]))
    assert listing.json()[0]["name"] == "My Best Friend"


async def test_rename_contact_clear_name(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    await client.post(
        f"{API}/contacts",
        json={"identifier": "alice"},
        headers=auth_headers(bob["access_token"]),
    )
    await client.patch(
        f"{API}/contacts/{alice['user']['id']}",
        json={"name": "Custom"},
        headers=auth_headers(bob["access_token"]),
    )
    cleared = await client.patch(
        f"{API}/contacts/{alice['user']['id']}",
        json={"name": None},
        headers=auth_headers(bob["access_token"]),
    )
    assert cleared.status_code == 200
    assert cleared.json()["name"] is None


async def test_rename_non_contact_404(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    response = await client.patch(
        f"{API}/contacts/{alice['user']['id']}",
        json={"name": "X"},
        headers=auth_headers(bob["access_token"]),
    )
    assert response.status_code == 404


async def test_rename_contact_empty_name_400(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    await client.post(
        f"{API}/contacts",
        json={"identifier": "alice"},
        headers=auth_headers(bob["access_token"]),
    )
    response = await client.patch(
        f"{API}/contacts/{alice['user']['id']}",
        json={"name": "   "},
        headers=auth_headers(bob["access_token"]),
    )
    assert response.status_code == 400
