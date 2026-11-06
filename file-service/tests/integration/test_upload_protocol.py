from pathlib import Path

import pytest
from httpx import AsyncClient

from tests.conftest import TEST_CHUNK_SIZE, TEST_INTERNAL_KEY
from tests.helpers import bearer, make_ticket, png_bytes, sha256_hex

BASE = "/files/v1/uploads"


def chunk_of(content: bytes, index: int) -> bytes:
    return content[index * TEST_CHUNK_SIZE : (index + 1) * TEST_CHUNK_SIZE]


async def put_chunk(client: AsyncClient, ticket: str, upload_id: str, content: bytes, index: int):
    return await client.put(
        f"{BASE}/{upload_id}/chunks/{index}",
        content=chunk_of(content, index),
        headers={**bearer(ticket), "Content-Type": "application/octet-stream"},
    )


async def test_full_protocol_stores_verified_file_and_announces_it(
    client: AsyncClient, settings, fake_redis
) -> None:
    content = png_bytes(TEST_CHUNK_SIZE * 2 + 300)
    upload_id, ticket = make_ticket(content, user_id=5)

    init = await client.post(BASE, headers=bearer(ticket))
    assert init.status_code == 201, init.text
    assert init.json() == {
        "upload_id": upload_id,
        "status": "active",
        "chunk_size": TEST_CHUNK_SIZE,
        "total_chunks": 3,
        "size_bytes": len(content),
        "received_chunks": [],
    }

    for index in (2, 0, 1):
        response = await put_chunk(client, ticket, upload_id, content, index)
        assert response.status_code == 200, response.text
        assert response.json()["index"] == index

    status = await client.get(f"{BASE}/{upload_id}", headers=bearer(ticket))
    assert status.json()["received_chunks"] == [0, 1, 2]

    complete = await client.post(f"{BASE}/{upload_id}/complete", headers=bearer(ticket))
    assert complete.status_code == 202, complete.text
    assert complete.json()["status"] == "completed"

    entries = await fake_redis.xrange("upload.completed")
    assert len(entries) == 1
    fields = entries[0][1]
    assert fields["type"] == "upload.completed"
    assert fields["upload_id"] == upload_id
    assert fields["sha256"] == sha256_hex(content)
    assert fields["ticket"] == ticket
    assert (settings.media_root / fields["file_path"]).read_bytes() == content
    assert not (settings.chunks_root / upload_id).exists()


async def test_resume_reports_only_received_chunks(client: AsyncClient) -> None:
    content = png_bytes(TEST_CHUNK_SIZE * 3)
    upload_id, ticket = make_ticket(content)
    await client.post(BASE, headers=bearer(ticket))
    await put_chunk(client, ticket, upload_id, content, 1)
    again = await client.post(BASE, headers=bearer(ticket))
    assert again.status_code == 200
    assert again.json()["received_chunks"] == [1]


async def test_resending_a_chunk_overwrites_it(client: AsyncClient) -> None:
    content = png_bytes(TEST_CHUNK_SIZE + 10)
    upload_id, ticket = make_ticket(content)
    await client.post(BASE, headers=bearer(ticket))
    for _ in range(2):
        assert (await put_chunk(client, ticket, upload_id, content, 0)).status_code == 200
    await put_chunk(client, ticket, upload_id, content, 1)
    complete = await client.post(f"{BASE}/{upload_id}/complete", headers=bearer(ticket))
    assert complete.status_code == 202


async def test_complete_with_missing_chunks_is_409_with_list(client: AsyncClient) -> None:
    content = png_bytes(TEST_CHUNK_SIZE * 3)
    upload_id, ticket = make_ticket(content)
    await client.post(BASE, headers=bearer(ticket))
    await put_chunk(client, ticket, upload_id, content, 1)
    response = await client.post(f"{BASE}/{upload_id}/complete", headers=bearer(ticket))
    assert response.status_code == 409
    assert response.json()["missing_chunks"] == [0, 2]


async def test_checksum_mismatch_is_422_and_leaves_no_file(
    client: AsyncClient, settings, fake_redis
) -> None:
    content = png_bytes(500)
    upload_id, ticket = make_ticket(content, sha256="1" * 64)
    await client.post(BASE, headers=bearer(ticket))
    await put_chunk(client, ticket, upload_id, content, 0)
    response = await client.post(f"{BASE}/{upload_id}/complete", headers=bearer(ticket))
    assert response.status_code == 422
    assert list((settings.media_root / "artifacts").iterdir()) == []
    assert await fake_redis.xlen("upload.completed") == 0
    status = await client.get(f"{BASE}/{upload_id}", headers=bearer(ticket))
    assert status.json()["status"] == "failed"


async def test_mime_mismatch_is_422(client: AsyncClient) -> None:
    content = png_bytes(500)
    upload_id, ticket = make_ticket(content, mime_type="video/mp4")
    await client.post(BASE, headers=bearer(ticket))
    await put_chunk(client, ticket, upload_id, content, 0)
    response = await client.post(f"{BASE}/{upload_id}/complete", headers=bearer(ticket))
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("body_size", "status"),
    [(TEST_CHUNK_SIZE + 1, 413), (TEST_CHUNK_SIZE - 1, 400)],
)
async def test_chunk_with_wrong_length_is_rejected(
    client: AsyncClient, body_size: int, status: int
) -> None:
    content = png_bytes(TEST_CHUNK_SIZE * 2)
    upload_id, ticket = make_ticket(content)
    await client.post(BASE, headers=bearer(ticket))
    response = await client.put(
        f"{BASE}/{upload_id}/chunks/0", content=b"x" * body_size, headers=bearer(ticket)
    )
    assert response.status_code == status


async def test_chunk_index_out_of_range_is_400(client: AsyncClient) -> None:
    content = png_bytes(100)
    upload_id, ticket = make_ticket(content)
    await client.post(BASE, headers=bearer(ticket))
    response = await client.put(
        f"{BASE}/{upload_id}/chunks/1", content=b"x", headers=bearer(ticket)
    )
    assert response.status_code == 400


@pytest.mark.parametrize("case", ["missing", "expired", "other_upload", "tampered"])
async def test_bad_tickets_are_401(client: AsyncClient, case: str) -> None:
    content = png_bytes(100)
    upload_id, ticket = make_ticket(content)
    await client.post(BASE, headers=bearer(ticket))
    headers = bearer(ticket)
    if case == "missing":
        headers = {}
    elif case == "expired":
        headers = bearer(make_ticket(content, upload_id=upload_id, ttl_seconds=-1)[1])
    elif case == "other_upload":
        headers = bearer(make_ticket(content)[1])
    else:
        headers = bearer(ticket[:-3] + "abc")
    response = await client.get(f"{BASE}/{upload_id}", headers=headers)
    assert response.status_code == 401


async def test_upload_of_another_user_is_401(client: AsyncClient) -> None:
    content = png_bytes(100)
    upload_id, ticket = make_ticket(content, user_id=1)
    await client.post(BASE, headers=bearer(ticket))
    _, foreign = make_ticket(content, upload_id=upload_id, user_id=2)
    response = await client.get(f"{BASE}/{upload_id}", headers=bearer(foreign))
    assert response.status_code == 401


async def test_oversized_upload_is_413_at_init(client: AsyncClient) -> None:
    _, ticket = make_ticket(b"x", size_bytes=64 * 1024 + 1)
    assert (await client.post(BASE, headers=bearer(ticket))).status_code == 413


async def test_abort_removes_chunks(client: AsyncClient, settings) -> None:
    content = png_bytes(TEST_CHUNK_SIZE * 2)
    upload_id, ticket = make_ticket(content)
    await client.post(BASE, headers=bearer(ticket))
    await put_chunk(client, ticket, upload_id, content, 0)
    response = await client.delete(f"{BASE}/{upload_id}", headers=bearer(ticket))
    assert response.status_code == 204
    assert not (settings.chunks_root / upload_id).exists()
    later = await put_chunk(client, ticket, upload_id, content, 1)
    assert later.status_code == 409


async def test_no_file_is_visible_in_media_before_verification(
    client: AsyncClient, settings
) -> None:
    content = png_bytes(TEST_CHUNK_SIZE * 2)
    upload_id, ticket = make_ticket(content)
    await client.post(BASE, headers=bearer(ticket))
    await put_chunk(client, ticket, upload_id, content, 0)
    await put_chunk(client, ticket, upload_id, content, 1)
    media = Path(settings.media_root)
    assert [p for p in media.rglob("*") if p.is_file()] == []


async def test_internal_api_requires_key(client: AsyncClient) -> None:
    body = {"older_than_seconds": 0}
    assert (await client.post("/internal/v1/cleanup/terminal", json=body)).status_code == 401
    wrong = {"X-Internal-Key": "nope"}
    assert (
        await client.post("/internal/v1/cleanup/terminal", json=body, headers=wrong)
    ).status_code == 401
    ok = await client.post(
        "/internal/v1/cleanup/terminal", json=body, headers={"X-Internal-Key": TEST_INTERNAL_KEY}
    )
    assert ok.status_code == 200
    assert ok.json() == {"rule": "terminal", "purged": [], "skipped": []}


async def test_internal_cleanup_purges_aborted_upload(client: AsyncClient, settings) -> None:
    content = png_bytes(TEST_CHUNK_SIZE * 2)
    upload_id, ticket = make_ticket(content)
    await client.post(BASE, headers=bearer(ticket))
    await client.delete(f"{BASE}/{upload_id}", headers=bearer(ticket))
    response = await client.post(
        "/internal/v1/cleanup/terminal",
        json={"older_than_seconds": 0},
        headers={"X-Internal-Key": TEST_INTERNAL_KEY},
    )
    assert response.json()["purged"] == [upload_id]
    status = await client.get(f"{BASE}/{upload_id}", headers=bearer(ticket))
    assert status.json()["status"] == "purged"


async def test_health(client: AsyncClient) -> None:
    assert (await client.get("/health")).json() == {"status": "ok"}
