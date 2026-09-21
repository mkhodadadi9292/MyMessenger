import pytest

from app.config import Settings
from tests.helpers import (
    API_V1,
    auth_headers,
    login_user,
    register_user,
    request_otp,
    verify_otp,
)

API = API_V1


@pytest.fixture
def settings(request, tmp_path) -> Settings:
    otp_ttl = getattr(request, "param", 300)
    return Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        media_root=tmp_path / "media",
        jwt_secret="test-secret-0123456789-0123456789",
        otp_ttl_seconds=otp_ttl,
        _env_file=None,
    )


async def test_request_otp_contract(client) -> None:
    body = await request_otp(client, "alice@example.com")
    assert body["delivery"] == "log"
    assert body["expires_in"] == 300
    assert "otp_id" in body


async def test_verify_without_prior_request_400(client) -> None:
    response = await client.post(
        f"{API}/auth/otp/verify",
        json={"identifier": "nobody@example.com", "code": "000000"},
    )
    assert response.status_code == 400
    assert "detail" in response.json()


async def test_verify_wrong_code_400(client) -> None:
    await request_otp(client, "alice@example.com")
    response = await client.post(
        f"{API}/auth/otp/verify",
        json={"identifier": "alice@example.com", "code": "000000"},
    )
    assert response.status_code == 400


async def test_otp_single_use(client, otp_sender) -> None:
    identifier = "alice@example.com"
    await request_otp(client, identifier)
    code = otp_sender.code_for(identifier)
    first = await verify_otp(client, identifier, code)
    assert first.get("registered") is False
    replay = await client.post(
        f"{API}/auth/otp/verify", json={"identifier": identifier, "code": code}
    )
    assert replay.status_code == 400


@pytest.mark.parametrize("settings", [0], indirect=True)
async def test_expired_otp_rejected(client, otp_sender) -> None:
    identifier = "alice@example.com"
    await request_otp(client, identifier)
    response = await client.post(
        f"{API}/auth/otp/verify",
        json={"identifier": identifier, "code": otp_sender.code_for(identifier)},
    )
    assert response.status_code == 400


async def test_register_creates_account(client, otp_sender) -> None:
    tokens = await register_user(client, otp_sender, "alice@example.com", "alice", "Alice")
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["user"]["username"] == "alice"
    assert "phone" not in tokens["user"]


async def test_register_duplicate_username_409(client, otp_sender, user_factory) -> None:
    await user_factory(username="alice")
    await request_otp(client, "bob@example.com")
    verified = await verify_otp(client, "bob@example.com", otp_sender.code_for("bob@example.com"))
    response = await client.post(
        f"{API}/auth/register",
        json={
            "registration_token": verified["registration_token"],
            "username": "alice",
            "first_name": "Bob",
        },
    )
    assert response.status_code == 409


async def test_register_invalid_username_400(client, otp_sender) -> None:
    await request_otp(client, "bob@example.com")
    verified = await verify_otp(client, "bob@example.com", otp_sender.code_for("bob@example.com"))
    response = await client.post(
        f"{API}/auth/register",
        json={
            "registration_token": verified["registration_token"],
            "username": "BAD NAME!",
            "first_name": "Bob",
        },
    )
    assert response.status_code == 400


async def test_register_invalid_registration_token_400(client) -> None:
    response = await client.post(
        f"{API}/auth/register",
        json={"registration_token": "junk", "username": "bob", "first_name": "B"},
    )
    assert response.status_code == 400


async def test_login_flow(client, otp_sender, user_factory) -> None:
    identifier = "alice@example.com"
    await user_factory(username="alice", identifier=identifier)
    tokens = await login_user(client, otp_sender, identifier)
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["user"]["username"] == "alice"


async def test_refresh_rotates_and_revokes_old(client, user_factory) -> None:
    tokens = await user_factory()
    response = await client.post(
        f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert response.status_code == 200
    refreshed = response.json()
    assert refreshed["access_token"]
    assert refreshed["refresh_token"]
    replay = await client.post(
        f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert replay.status_code == 401


async def test_refresh_invalid_token_401(client) -> None:
    response = await client.post(f"{API}/auth/refresh", json={"refresh_token": "junk"})
    assert response.status_code == 401


async def test_logout_revokes_refresh(client, user_factory) -> None:
    tokens = await user_factory()
    logout = await client.post(
        f"{API}/auth/logout", json={"refresh_token": tokens["refresh_token"]}
    )
    assert logout.status_code == 200
    replay = await client.post(
        f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert replay.status_code == 401


async def test_garbage_access_token_401(client) -> None:
    response = await client.get(f"{API}/users/me", headers=auth_headers("junk"))
    assert response.status_code == 401


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/users/me"),
        ("PATCH", "/users/me"),
        ("GET", "/users/search?q=x"),
        ("GET", "/contacts"),
        ("POST", "/contacts"),
        ("GET", "/blocked"),
        ("POST", "/blocked/1"),
        ("GET", "/chats"),
        ("POST", "/chats/private"),
        ("GET", "/chats/1/messages"),
        ("GET", "/me/invites"),
    ],
)
async def test_protected_endpoints_require_auth(client, method: str, path: str) -> None:
    response = await client.request(method, f"{API}{path}")
    assert response.status_code == 401
