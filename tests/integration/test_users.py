from tests.helpers import API_V1, auth_headers

API = API_V1


async def test_get_me(client, user_factory) -> None:
    tokens = await user_factory(username="alice", first_name="Alice", last_name="Smith")
    response = await client.get(f"{API}/users/me", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "alice"
    assert body["first_name"] == "Alice"
    assert body["last_name"] == "Smith"
    assert "phone" not in body
    assert "email" not in body


async def test_patch_profile(client, user_factory) -> None:
    tokens = await user_factory()
    response = await client.patch(
        f"{API}/users/me",
        json={"first_name": "New", "bio": "hi there"},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["first_name"] == "New"
    assert body["bio"] == "hi there"


async def test_patch_username_taken_409(client, user_factory) -> None:
    await user_factory(username="taken")
    tokens = await user_factory(username="bob")
    response = await client.patch(
        f"{API}/users/me",
        json={"username": "taken"},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 409


async def test_patch_invalid_username_400(client, user_factory) -> None:
    tokens = await user_factory()
    response = await client.patch(
        f"{API}/users/me",
        json={"username": "BAD NAME"},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 400


async def test_get_user_by_id(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    tokens = await user_factory(username="bob")
    response = await client.get(
        f"{API}/users/{alice['user']['id']}", headers=auth_headers(tokens["access_token"])
    )
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "alice"
    assert "phone" not in body


async def test_get_unknown_user_404(client, user_factory) -> None:
    tokens = await user_factory()
    response = await client.get(
        f"{API}/users/999999", headers=auth_headers(tokens["access_token"])
    )
    assert response.status_code == 404


async def test_search_by_username_prefix(client, user_factory) -> None:
    await user_factory(username="alice")
    await user_factory(username="alex")
    await user_factory(username="bob")
    tokens = await user_factory(username="zoe")
    response = await client.get(
        f"{API}/users/search", params={"q": "al"}, headers=auth_headers(tokens["access_token"])
    )
    assert response.status_code == 200
    assert {u["username"] for u in response.json()} == {"alice", "alex"}


async def test_search_by_exact_phone_hides_phone(client, user_factory) -> None:
    await user_factory(username="alice", identifier="+989123456789")
    tokens = await user_factory(username="bob")
    response = await client.get(
        f"{API}/users/search",
        params={"q": "+989123456789"},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    results = response.json()
    assert [u["username"] for u in results] == ["alice"]
    assert all("phone" not in u for u in results)


async def test_search_missing_query_422(client, user_factory) -> None:
    tokens = await user_factory()
    response = await client.get(f"{API}/users/search", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 422


async def test_upload_avatar(client, user_factory) -> None:
    tokens = await user_factory()
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    response = await client.post(
        f"{API}/users/me/avatar",
        files={"file": ("avatar.png", png, "image/png")},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["avatar_url"]
    assert "/media/" in body["avatar_url"]


async def test_upload_avatar_rejects_non_image(client, user_factory) -> None:
    tokens = await user_factory()
    response = await client.post(
        f"{API}/users/me/avatar",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 400
