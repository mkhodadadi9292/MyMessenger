import hashlib
import time
import uuid

import jwt

TEST_TICKET_SECRET = "test-upload-ticket-secret-0123456789-abcdef"
TEST_ISSUER = "messenger-backend"
TEST_AUDIENCE = "file-service"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def png_bytes(size: int) -> bytes:
    body = bytes((i * 31 + 7) % 256 for i in range(size - len(PNG_SIGNATURE)))
    return PNG_SIGNATURE + body


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def new_upload_id() -> str:
    return uuid.uuid4().hex


def make_ticket(
    content: bytes,
    *,
    upload_id: str | None = None,
    user_id: int = 1,
    mime_type: str = "image/png",
    size_bytes: int | None = None,
    sha256: str | None = None,
    ttl_seconds: int = 600,
    secret: str = TEST_TICKET_SECRET,
    audience: str = TEST_AUDIENCE,
    issuer: str = TEST_ISSUER,
    typ: str = "upload",
) -> tuple[str, str]:
    upload_id = upload_id or new_upload_id()
    now = int(time.time())
    claims = {
        "iss": issuer,
        "aud": audience,
        "typ": typ,
        "sub": str(user_id),
        "upload_id": upload_id,
        "chat_id": 1,
        "kind": mime_type.split("/")[0],
        "mime_type": mime_type,
        "size_bytes": len(content) if size_bytes is None else size_bytes,
        "sha256": sha256 or sha256_hex(content),
        "file_name": "file.bin",
        "reply_to_id": None,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    return upload_id, jwt.encode(claims, secret, algorithm="HS256")


def bearer(ticket: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {ticket}"}
