import json
from datetime import datetime, timedelta
from pathlib import Path

import fakeredis
import jwt
import pytest

from app.config import Settings
from app.domain.exceptions import UnauthorizedError, ValidationError
from app.domain.time import utcnow
from app.domain.uploads import UploadRequest, UploadTicketClaims, is_stored_artifact_path
from app.domain.value_objects import ArtifactKind
from app.infrastructure.auth.upload_ticket import JwtUploadTicketCodec
from app.infrastructure.streams import RedisUploadOutcomePublisher

CONTRACT = json.loads(
    (Path(__file__).resolve().parents[2] / "contracts" / "upload-events.v1.json").read_text()
)
SECRET = "unit-upload-secret-0123456789-0123456789"
SHA = "a" * 64


def codec(secret: str = SECRET) -> JwtUploadTicketCodec:
    return JwtUploadTicketCodec(secret, "messenger-backend", "file-service", 60)


def claims(issued_at: datetime | None = None, reply_to_id: int | None = 3) -> UploadTicketClaims:
    return UploadTicketClaims(
        upload_id="f" * 32,
        user_id=7,
        chat_id=9,
        kind=ArtifactKind.VIDEO,
        mime_type="video/mp4",
        size_bytes=1234,
        sha256=SHA,
        file_name="clip.mp4",
        reply_to_id=reply_to_id,
        issued_at=(issued_at or utcnow()).replace(microsecond=0),
    )


def test_ticket_round_trip_keeps_every_claim() -> None:
    original = claims()
    issued = codec().issue(original)
    assert issued.upload_id == original.upload_id
    assert codec().read(issued.token) == original


def test_expired_ticket_is_still_readable_for_late_completion_events() -> None:
    old = claims(issued_at=utcnow() - timedelta(hours=2))
    assert codec().read(codec().issue(old).token) == old


def test_ticket_from_another_secret_is_rejected() -> None:
    token = codec("other-secret-0123456789-0123456789-xx").issue(claims()).token
    with pytest.raises(UnauthorizedError):
        codec().read(token)


def test_user_access_token_is_not_an_upload_ticket() -> None:
    token = jwt.encode(
        {"sub": "1", "type": "access", "iat": 1, "exp": 9999999999}, SECRET, algorithm="HS256"
    )
    with pytest.raises(UnauthorizedError):
        codec().read(token)


def test_null_reply_survives_round_trip() -> None:
    original = claims(reply_to_id=None)
    assert codec().read(codec().issue(original).token).reply_to_id is None


def request(**overrides) -> UploadRequest:
    values = dict(
        file_name="a.png", size_bytes=10, mime_type="image/png", kind=ArtifactKind.IMAGE, sha256=SHA
    )
    values.update(overrides)
    return UploadRequest(**values)


def test_valid_upload_request_passes() -> None:
    request().validate(max_size_bytes=10)


@pytest.mark.parametrize(
    "overrides",
    [
        {"size_bytes": 11},
        {"size_bytes": 0},
        {"file_name": " "},
        {"file_name": "x" * 256},
        {"mime_type": "video/mp4"},
        {"sha256": "A" * 64},
        {"sha256": "abc"},
    ],
)
def test_invalid_upload_request_is_rejected(overrides: dict) -> None:
    with pytest.raises(ValidationError):
        request(**overrides).validate(max_size_bytes=10)


@pytest.mark.parametrize(
    ("path", "valid"),
    [
        (f"artifacts/{'0' * 32}.png", True),
        (f"artifacts/{'0' * 32}.webm", True),
        ("artifacts/../secret.png", False),
        (f"avatars/{'0' * 32}.png", False),
        (f"/artifacts/{'0' * 32}.png", False),
        (f"artifacts/{'0' * 32}", False),
    ],
)
def test_stored_artifact_path_pattern(path: str, valid: bool) -> None:
    assert is_stored_artifact_path(path) is valid


def test_default_stream_names_match_contract() -> None:
    settings = Settings(_env_file=None)
    assert settings.completed_stream == CONTRACT["streams"]["completed"]
    assert settings.outcome_stream == CONTRACT["streams"]["outcome"]
    assert settings.upload_consumer_group == CONTRACT["groups"]["completed"]


async def test_outcome_events_carry_contract_fields() -> None:
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    publisher = RedisUploadOutcomePublisher(redis, "upload.outcome", 100)
    await publisher.publish_attached("a" * 32, 42, 7)
    await publisher.publish_rejected("b" * 32, "not_member")
    (_, attached), (_, rejected) = await redis.xrange("upload.outcome")
    required = set(CONTRACT["upload.outcome"]["required_fields"])
    examples = {e["type"]: set(e) for e in CONTRACT["upload.outcome"]["examples"]}
    assert required <= set(attached) and set(attached) == examples["upload.attached"]
    assert required <= set(rejected) and set(rejected) == examples["upload.rejected"]
    await redis.aclose()


def test_contract_example_completion_parses() -> None:
    from app.api.upload_events import parse_completed_upload

    upload = parse_completed_upload(CONTRACT["upload.completed"]["example"])
    assert upload.size_bytes == 1048577
    assert upload.file_path.startswith("artifacts/")
