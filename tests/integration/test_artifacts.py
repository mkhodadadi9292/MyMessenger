import pytest

from app.config import Settings
from tests.helpers import API_V1, auth_headers
from tests.uploads import request_ticket, upload_artifact

API = API_V1

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 128
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 128
MP3 = b"ID3" + b"\x00" * 128


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        media_root=tmp_path / "media",
        jwt_secret="test-secret-0123456789-0123456789",
        upload_ticket_secret="test-upload-ticket-secret-0123456789-abcdef",
        redis_url=None,
        max_artifact_size_mb=1,
        _env_file=None,
    )


async def _open_chat(client, alice: dict, bob: dict) -> int:
    response = await client.post(
        f"{API}/chats/private",
        json={"user_id": alice["user"]["id"]},
        headers=auth_headers(bob["access_token"]),
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


async def test_upload_image(app, client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)

    message = await upload_artifact(
        app, client, alice, chat_id, "pic.png", PNG, "image/png", "image"
    )
    assert message["text"] is None
    artifact = message["artifact"]
    assert artifact["kind"] == "image"
    assert artifact["file_name"] == "pic.png"
    assert artifact["mime_type"] == "image/png"
    assert artifact["size_bytes"] == len(PNG)
    assert artifact["url"].startswith("/media/artifacts/")


@pytest.mark.parametrize(
    ("file_name", "content", "mime", "kind"),
    [
        ("clip.mp4", MP4, "video/mp4", "video"),
        ("song.mp3", MP3, "audio/mpeg", "audio"),
    ],
)
async def test_upload_video_and_audio(
    app, client, user_factory, file_name: str, content: bytes, mime: str, kind: str
) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    message = await upload_artifact(app, client, alice, chat_id, file_name, content, mime, kind)
    assert message["artifact"]["kind"] == kind
    assert message["artifact"]["mime_type"] == mime


async def test_upload_kind_mismatch_400(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    response = await request_ticket(client, alice, chat_id, "pic.png", PNG, "image/png", "video")
    assert response.status_code == 400


async def test_upload_unsupported_mime_400(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    response = await request_ticket(
        client, alice, chat_id, "notes.txt", b"hello", "text/plain", "image"
    )
    assert response.status_code == 400


async def test_upload_unknown_kind_422(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    response = await request_ticket(client, alice, chat_id, "pic.png", PNG, "image/png", "document")
    assert response.status_code == 422


async def test_upload_with_reply(app, client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    first = await client.post(
        f"{API}/chats/{chat_id}/messages",
        json={"text": "look at this"},
        headers=auth_headers(alice["access_token"]),
    )
    message = await upload_artifact(
        app, client, bob, chat_id, "pic.png", PNG, "image/png", "image",
        reply_to_id=first.json()["id"],
    )
    assert message["reply_to_id"] == first.json()["id"]
    assert message["reply_to"]["text"] == "look at this"


async def test_upload_oversized_400(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    big = b"\x00" * (1024 * 1024 + 1)
    response = await request_ticket(client, alice, chat_id, "big.png", big, "image/png", "image")
    assert response.status_code == 400


async def test_upload_non_member_403(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    carol = await user_factory(username="carol")
    chat_id = await _open_chat(client, alice, bob)
    response = await request_ticket(client, carol, chat_id, "pic.png", PNG, "image/png", "image")
    assert response.status_code == 403


async def test_download_artifact(app, client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    message = await upload_artifact(
        app, client, alice, chat_id, "pic.png", PNG, "image/png", "image"
    )

    response = await client.get(
        f"{API}/artifacts/{message['artifact']['id']}/download",
        headers=auth_headers(bob["access_token"]),
    )
    assert response.status_code == 200
    assert response.content == PNG
    assert response.headers["content-type"] == "image/png"


async def test_download_non_member_403(app, client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    carol = await user_factory(username="carol")
    chat_id = await _open_chat(client, alice, bob)
    message = await upload_artifact(
        app, client, alice, chat_id, "pic.png", PNG, "image/png", "image"
    )
    response = await client.get(
        f"{API}/artifacts/{message['artifact']['id']}/download",
        headers=auth_headers(carol["access_token"]),
    )
    assert response.status_code == 403


async def test_download_unknown_artifact_404(client, user_factory) -> None:
    tokens = await user_factory()
    response = await client.get(
        f"{API}/artifacts/999999/download", headers=auth_headers(tokens["access_token"])
    )
    assert response.status_code == 404


async def test_multipart_upload_endpoint_is_gone(client, user_factory) -> None:
    alice = await user_factory(username="alice")
    bob = await user_factory(username="bob")
    chat_id = await _open_chat(client, alice, bob)
    response = await client.post(
        f"{API}/chats/{chat_id}/artifacts",
        files={"file": ("pic.png", PNG, "image/png")},
        data={"kind": "image"},
        headers=auth_headers(alice["access_token"]),
    )
    assert response.status_code in (404, 405)
