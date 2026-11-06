import json
from datetime import datetime
from pathlib import Path

import fakeredis

from file_service.config import Settings
from file_service.domain.events import UploadCompleted
from file_service.infrastructure.streams import RedisCompletionPublisher

CONTRACT = json.loads(
    (Path(__file__).resolve().parents[3] / "contracts" / "upload-events.v1.json").read_text()
)


def test_default_stream_and_group_names_match_contract() -> None:
    settings = Settings(_env_file=None)
    assert settings.completed_stream == CONTRACT["streams"]["completed"]
    assert settings.outcome_stream == CONTRACT["streams"]["outcome"]
    assert settings.backend_group == CONTRACT["groups"]["completed"]
    assert settings.outcome_group == CONTRACT["groups"]["outcome"]


async def test_published_completion_has_exactly_the_contract_fields() -> None:
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    publisher = RedisCompletionPublisher(redis, "upload.completed", 1000)
    await publisher.publish_completed(
        UploadCompleted(
            upload_id="a" * 32,
            ticket="t",
            file_path="artifacts/x.png",
            size_bytes=3,
            sha256="0" * 64,
            mime_type="image/png",
            completed_at=datetime(2026, 1, 1),
        )
    )
    [(_, fields)] = await redis.xrange("upload.completed")
    assert sorted(fields) == sorted(CONTRACT["upload.completed"]["required_fields"])
    assert fields["type"] == "upload.completed"
    assert fields["completed_at"] == "2026-01-01T00:00:00Z"
    await redis.aclose()


def test_outcome_types_match_contract() -> None:
    from file_service.domain.events import UPLOAD_ATTACHED, UPLOAD_REJECTED

    assert sorted(CONTRACT["upload.outcome"]["types"]) == sorted([UPLOAD_ATTACHED, UPLOAD_REJECTED])
