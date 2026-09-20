from httpx import AsyncClient

from tests.helpers import auth_headers, login_user, register_user

API = "/api/v1"


async def test_full_auth_journey(live_client: AsyncClient, otp_sender) -> None:
    client = live_client
    tokens = await register_user(client, otp_sender, "alice@example.com", "alice", "Alice")

    me = await client.get(f"{API}/users/me", headers=auth_headers(tokens["access_token"]))
    assert me.status_code == 200
    assert me.json()["username"] == "alice"

    patched = await client.patch(
        f"{API}/users/me",
        json={"bio": "hello world"},
        headers=auth_headers(tokens["access_token"]),
    )
    assert patched.status_code == 200
    assert patched.json()["bio"] == "hello world"

    refreshed = await client.post(
        f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 200

    logout = await client.post(
        f"{API}/auth/logout", json={"refresh_token": refreshed.json()["refresh_token"]}
    )
    assert logout.status_code == 200
    replay = await client.post(
        f"{API}/auth/refresh", json={"refresh_token": refreshed.json()["refresh_token"]}
    )
    assert replay.status_code == 401

    relogin = await login_user(client, otp_sender, "alice@example.com")
    assert "access_token" in relogin


async def test_search_journey(live_client: AsyncClient, otp_sender) -> None:
    client = live_client
    await register_user(client, otp_sender, "alice@example.com", "alice", "Alice")
    bob = await register_user(client, otp_sender, "bob@example.com", "bob", "Bob")

    results = await client.get(
        f"{API}/users/search", params={"q": "al"}, headers=auth_headers(bob["access_token"])
    )
    assert results.status_code == 200
    assert [u["username"] for u in results.json()] == ["alice"]
    assert all("phone" not in u for u in results.json())
