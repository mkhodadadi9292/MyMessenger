import hashlib

import jwt
import pytest

from app.config import Settings
from app.main import create_app
from tests.conftest import TEST_UPLOAD_TICKET_SECRET
from tests.helpers import API_V1, auth_headers
from tests.uploads import request_ticket

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


async def _open_chat(client, alice: dict, bob: dict) -> int:
    response = await client.post(
        f"{API_V1}/chats/private",
        json={"user_id": alice["user"]["id"]},
        headers=auth_headers(bob["access_token"]),
    )
    return response.json()["id"]


def _claims(token: str) -> dict:
    return jwt.decode(
        token,
        TEST_UPLOAD_TICKET_SECRET,
        algorithms=["HS256"],
        audience="file-service",
        issuer="messenger-backend",
    )


async def test_member_gets_signed_ticket_with_upload_claims(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    response = await request_ticket(client, alice, chat_id, "pic.png", PNG, "image/png", "image")
    assert response.status_code == 201
    body = response.json()
    assert body["upload_url"] == "/files/v1/uploads"
    assert len(body["upload_id"]) == 32
    claims = _claims(body["ticket"])
    assert claims["typ"] == "upload"
    assert claims["sub"] == str(alice["user"]["id"])
    assert claims["upload_id"] == body["upload_id"]
    assert claims["chat_id"] == chat_id
    assert claims["kind"] == "image"
    assert claims["mime_type"] == "image/png"
    assert claims["size_bytes"] == len(PNG)
    assert claims["sha256"] == hashlib.sha256(PNG).hexdigest()
    assert claims["file_name"] == "pic.png"
    assert claims["reply_to_id"] is None
    assert claims["exp"] - claims["iat"] == 3600


async def test_each_ticket_has_a_fresh_upload_id(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    first = await request_ticket(client, alice, chat_id, "a.png", PNG, "image/png", "image")
    second = await request_ticket(client, alice, chat_id, "a.png", PNG, "image/png", "image")
    assert first.json()["upload_id"] != second.json()["upload_id"]


async def test_ticket_is_not_signed_with_the_user_jwt_secret(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    ticket = (
        await request_ticket(client, alice, chat_id, "a.png", PNG, "image/png", "image")
    ).json()["ticket"]
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(
            ticket,
            "test-secret-0123456789-0123456789",
            algorithms=["HS256"],
            audience="file-service",
        )


async def test_ticket_cannot_be_used_as_access_token(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    ticket = (
        await request_ticket(client, alice, chat_id, "a.png", PNG, "image/png", "image")
    ).json()["ticket"]
    assert (await client.get(f"{API_V1}/users/me", headers=auth_headers(ticket))).status_code == 401


async def test_blocked_pair_cannot_get_ticket(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    await client.post(
        f"{API_V1}/blocked/{alice['user']['id']}", headers=auth_headers(bob["access_token"])
    )
    response = await request_ticket(client, alice, chat_id, "a.png", PNG, "image/png", "image")
    assert response.status_code == 403


async def test_unknown_chat_is_404(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    response = await request_ticket(client, alice, 9999, "a.png", PNG, "image/png", "image")
    assert response.status_code == 404


@pytest.mark.parametrize(
    "override",
    [{"sha256": "XYZ"}, {"sha256": "A" * 64}, {"file_name": ""}, {"file_name": "x" * 256},
     {"size_bytes": 0}, {"size_bytes": -5}],
)
async def test_invalid_upload_request_is_400(client, user_factory, override: dict) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    body = {
        "file_name": "a.png",
        "size_bytes": len(PNG),
        "mime_type": "image/png",
        "kind": "image",
        "sha256": hashlib.sha256(PNG).hexdigest(),
        **override,
    }
    response = await client.post(
        f"{API_V1}/chats/{chat_id}/uploads", json=body, headers=auth_headers(alice["access_token"])
    )
    assert response.status_code == 400


async def test_reply_target_must_exist_and_be_in_the_same_chat(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    carol = await user_factory(username="carol")
    chat_id = await _open_chat(client, alice, bob)
    other_chat = await _open_chat(client, alice, carol)
    elsewhere = await client.post(
        f"{API_V1}/chats/{other_chat}/messages",
        json={"text": "elsewhere"},
        headers=auth_headers(alice["access_token"]),
    )
    missing = await request_ticket(
        client, alice, chat_id, "a.png", PNG, "image/png", "image", reply_to_id=99999
    )
    assert missing.status_code == 404
    foreign = await request_ticket(
        client, alice, chat_id, "a.png", PNG, "image/png", "image",
        reply_to_id=elsewhere.json()["id"],
    )
    assert foreign.status_code == 400


async def test_unauthenticated_ticket_request_is_401(client) -> None:
    response = await client.post(f"{API_V1}/chats/1/uploads", json={})
    assert response.status_code == 401


def test_app_refuses_upload_secret_equal_to_jwt_secret(tmp_path) -> None:
    settings = Settings(
        database_url="sqlite+aiosqlite://",
        media_root=tmp_path,
        jwt_secret="same-secret-0123456789-0123456789",
        upload_ticket_secret="same-secret-0123456789-0123456789",
        _env_file=None,
    )
    with pytest.raises(RuntimeError, match="UPLOAD_TICKET_SECRET"):
        create_app(settings)
