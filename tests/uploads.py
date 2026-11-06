import hashlib
import uuid
from dataclasses import dataclass

from fastapi import FastAPI
from httpx import AsyncClient

from app.api.upload_events import UploadCompletedHandler
from tests.fakes import RecordingOutcomePublisher
from tests.helpers import API_V1, auth_headers

EXTENSIONS = {
    "image/png": ".png",
    "video/mp4": ".mp4",
    "audio/mpeg": ".mp3",
}


@dataclass
class TicketedUpload:
    upload_id: str
    ticket: str
    content: bytes
    mime_type: str


async def request_ticket(
    client: AsyncClient,
    sender: dict,
    chat_id: int,
    file_name: str,
    content: bytes,
    mime_type: str,
    kind: str,
    reply_to_id: int | None = None,
):
    return await client.post(
        f"{API_V1}/chats/{chat_id}/uploads",
        json={
            "file_name": file_name,
            "size_bytes": len(content),
            "mime_type": mime_type,
            "kind": kind,
            "sha256": hashlib.sha256(content).hexdigest(),
            "reply_to_id": reply_to_id,
        },
        headers=auth_headers(sender["access_token"]),
    )


def store_like_file_service(app: FastAPI, content: bytes, mime_type: str) -> str:
    relative = f"artifacts/{uuid.uuid4().hex}{EXTENSIONS.get(mime_type, '.bin')}"
    path = app.state.settings.media_root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return relative


def completed_event(upload: TicketedUpload, file_path: str) -> dict[str, str]:
    return {
        "schema_version": "1",
        "event_id": uuid.uuid4().hex,
        "type": "upload.completed",
        "upload_id": upload.upload_id,
        "ticket": upload.ticket,
        "file_path": file_path,
        "size_bytes": str(len(upload.content)),
        "sha256": hashlib.sha256(upload.content).hexdigest(),
        "mime_type": upload.mime_type,
        "completed_at": "2026-11-06T12:00:00Z",
    }


def completion_handler(
    app: FastAPI, publisher: RecordingOutcomePublisher | None = None
) -> UploadCompletedHandler:
    return UploadCompletedHandler(
        app.state.session_factory,
        app.state.realtime,
        publisher or RecordingOutcomePublisher(),
        app.state.settings,
    )


async def ticket_for(
    client: AsyncClient,
    sender: dict,
    chat_id: int,
    file_name: str,
    content: bytes,
    mime_type: str,
    kind: str,
    reply_to_id: int | None = None,
) -> TicketedUpload:
    response = await request_ticket(
        client, sender, chat_id, file_name, content, mime_type, kind, reply_to_id
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return TicketedUpload(body["upload_id"], body["ticket"], content, mime_type)


async def upload_artifact(
    app: FastAPI,
    client: AsyncClient,
    sender: dict,
    chat_id: int,
    file_name: str,
    content: bytes,
    mime_type: str,
    kind: str,
    reply_to_id: int | None = None,
) -> dict:
    upload = await ticket_for(
        client, sender, chat_id, file_name, content, mime_type, kind, reply_to_id
    )
    publisher = RecordingOutcomePublisher()
    file_path = store_like_file_service(app, content, mime_type)
    await completion_handler(app, publisher)(completed_event(upload, file_path))
    assert publisher.rejected == [], publisher.rejected
    [(_, message_id, _)] = publisher.attached
    history = await client.get(
        f"{API_V1}/chats/{chat_id}/messages", headers=auth_headers(sender["access_token"])
    )
    return next(m for m in history.json() if m["id"] == message_id)
