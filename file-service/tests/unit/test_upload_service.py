import pytest

from file_service.application.outbox_relay import OutboxRelay
from file_service.application.upload_service import UploadService
from file_service.domain.exceptions import (
    ConflictError,
    LengthRequiredError,
    MissingChunksError,
    PayloadTooLargeError,
    UnauthorizedError,
    ValidationError,
    VerificationError,
)
from file_service.domain.upload_session import UploadStatus
from file_service.infrastructure.tickets import JwtTicketVerifier
from tests.fakes import (
    CountingTransaction,
    FixedClock,
    InMemoryChunkStore,
    InMemoryMediaStore,
    InMemorySessionRepository,
    RecordingPublisher,
    body_of,
)
from tests.helpers import (
    TEST_AUDIENCE,
    TEST_ISSUER,
    TEST_TICKET_SECRET,
    make_ticket,
    png_bytes,
    sha256_hex,
)

CHUNK = 64


class Harness:
    def __init__(self, publisher: RecordingPublisher | None = None, max_size: int = 10_000):
        self.sessions = InMemorySessionRepository()
        self.chunks = InMemoryChunkStore()
        self.media = InMemoryMediaStore(self.chunks)
        self.publisher = publisher or RecordingPublisher()
        self.clock = FixedClock()
        self.service = UploadService(
            sessions=self.sessions,
            transaction=CountingTransaction(),
            chunks=self.chunks,
            media=self.media,
            tickets=JwtTicketVerifier(TEST_TICKET_SECRET, TEST_ISSUER, TEST_AUDIENCE),
            publisher=self.publisher,
            clock=self.clock,
            chunk_size=CHUNK,
            max_upload_size_bytes=max_size,
        )

    async def put(self, token: str, upload_id: str, content: bytes, index: int) -> None:
        piece = content[index * CHUNK : (index + 1) * CHUNK]
        await self.service.put_chunk(token, upload_id, index, len(piece), body_of(piece, 10))

    async def put_all(self, token: str, upload_id: str, content: bytes, order=None) -> None:
        total = -(-len(content) // CHUNK)
        for index in order or range(total):
            await self.put(token, upload_id, content, index)


@pytest.fixture
def harness() -> Harness:
    return Harness()


async def test_init_creates_session_with_chunk_plan(harness: Harness) -> None:
    content = png_bytes(150)
    upload_id, token = make_ticket(content)
    state, created = await harness.service.init(token)
    assert created
    assert state.session.total_chunks == 3
    assert state.session.status is UploadStatus.ACTIVE
    assert state.received_chunks == []


async def test_init_is_idempotent_for_active_session(harness: Harness) -> None:
    content = png_bytes(150)
    upload_id, token = make_ticket(content)
    await harness.service.init(token)
    await harness.put(token, upload_id, content, 1)
    state, created = await harness.service.init(token)
    assert not created
    assert state.received_chunks == [1]


async def test_init_rejects_oversized_upload() -> None:
    harness = Harness(max_size=100)
    _, token = make_ticket(png_bytes(150))
    with pytest.raises(PayloadTooLargeError):
        await harness.service.init(token)


async def test_init_rejects_unsupported_mime(harness: Harness) -> None:
    _, token = make_ticket(b"plain text", mime_type="text/plain")
    with pytest.raises(ValidationError):
        await harness.service.init(token)


async def test_resending_a_chunk_is_idempotent(harness: Harness) -> None:
    content = png_bytes(150)
    upload_id, token = make_ticket(content)
    await harness.service.init(token)
    await harness.put(token, upload_id, content, 0)
    await harness.put(token, upload_id, content, 0)
    state = await harness.service.status(token, upload_id)
    assert state.received_chunks == [0]


async def test_out_of_order_chunks_complete_correctly(harness: Harness) -> None:
    content = png_bytes(200)
    upload_id, token = make_ticket(content)
    await harness.service.init(token)
    await harness.put_all(token, upload_id, content, order=[3, 1, 0, 2])
    state = await harness.service.complete(token, upload_id)
    assert state.session.status is UploadStatus.COMPLETED
    assert harness.media.files[state.session.file_path] == content


async def test_chunk_length_must_match_plan(harness: Harness) -> None:
    content = png_bytes(150)
    upload_id, token = make_ticket(content)
    await harness.service.init(token)
    with pytest.raises(PayloadTooLargeError):
        await harness.service.put_chunk(token, upload_id, 2, CHUNK, body_of(b"x" * CHUNK))
    with pytest.raises(ValidationError):
        await harness.service.put_chunk(token, upload_id, 0, 10, body_of(b"x" * 10))
    with pytest.raises(LengthRequiredError):
        await harness.service.put_chunk(token, upload_id, 0, None, body_of(b"x" * CHUNK))


async def test_chunk_index_out_of_range_is_rejected(harness: Harness) -> None:
    content = png_bytes(150)
    upload_id, token = make_ticket(content)
    await harness.service.init(token)
    with pytest.raises(ValidationError):
        await harness.service.put_chunk(token, upload_id, 3, CHUNK, body_of(b"x" * CHUNK))


async def test_body_longer_than_declared_length_is_cut_off(harness: Harness) -> None:
    content = png_bytes(150)
    upload_id, token = make_ticket(content)
    await harness.service.init(token)
    with pytest.raises(PayloadTooLargeError):
        await harness.service.put_chunk(token, upload_id, 0, CHUNK, body_of(b"x" * (CHUNK + 1)))
    assert harness.chunks.received(upload_id) == set()


async def test_complete_reports_missing_chunks(harness: Harness) -> None:
    content = png_bytes(200)
    upload_id, token = make_ticket(content)
    await harness.service.init(token)
    await harness.put_all(token, upload_id, content, order=[0, 2])
    with pytest.raises(MissingChunksError) as excinfo:
        await harness.service.complete(token, upload_id)
    assert excinfo.value.missing_chunks == [1, 3]
    assert (await harness.sessions.get(upload_id)).status is UploadStatus.ACTIVE


@pytest.mark.parametrize(
    ("ticket_overrides", "reason"),
    [
        ({"size_bytes": 151}, "size"),
        ({"sha256": "0" * 64}, "checksum"),
        ({"mime_type": "image/jpeg"}, "mime"),
    ],
)
async def test_complete_rejects_content_that_differs_from_ticket(
    harness: Harness, ticket_overrides: dict, reason: str
) -> None:
    content = png_bytes(150)
    upload_id, token = make_ticket(content, **ticket_overrides)
    await harness.service.init(token)
    if "size_bytes" in ticket_overrides:
        await harness.put_all(token, upload_id, content + b"\x00")
        harness.chunks.chunks[upload_id][2] = content[2 * CHUNK :]
    else:
        await harness.put_all(token, upload_id, content)
    with pytest.raises(VerificationError, match=reason):
        await harness.service.complete(token, upload_id)
    session = await harness.sessions.get(upload_id)
    assert session.status is UploadStatus.FAILED
    assert harness.media.files == {}
    assert harness.publisher.events == []


async def test_complete_publishes_event_and_is_idempotent(harness: Harness) -> None:
    content = png_bytes(150)
    upload_id, token = make_ticket(content)
    await harness.service.init(token)
    await harness.put_all(token, upload_id, content)
    first = await harness.service.complete(token, upload_id)
    second = await harness.service.complete(token, upload_id)
    assert first.session.file_path == second.session.file_path
    assert len(harness.publisher.events) == 1
    event = harness.publisher.events[0]
    assert event.upload_id == upload_id
    assert event.sha256 == sha256_hex(content)
    assert event.ticket == token
    assert event.file_path.startswith("artifacts/") and event.file_path.endswith(".png")
    assert harness.chunks.received(upload_id) == set()
    assert (await harness.sessions.get(upload_id)).completed_event_id == "1-0"


async def test_failed_publish_is_retried_by_outbox_relay() -> None:
    publisher = RecordingPublisher(fail=True)
    harness = Harness(publisher=publisher)
    content = png_bytes(100)
    upload_id, token = make_ticket(content)
    await harness.service.init(token)
    await harness.put_all(token, upload_id, content)
    await harness.service.complete(token, upload_id)
    assert (await harness.sessions.get(upload_id)).completed_event_id is None
    publisher.fail = False
    relay = OutboxRelay(harness.sessions, harness.service, harness.clock, min_age_seconds=30)
    assert await relay.relay_pending() == 0
    harness.clock.advance(31)
    assert await relay.relay_pending() == 1
    assert (await harness.sessions.get(upload_id)).completed_event_id == "1-0"


async def test_ticket_for_other_upload_is_rejected(harness: Harness) -> None:
    content = png_bytes(100)
    upload_id, token = make_ticket(content)
    _, other_token = make_ticket(content)
    await harness.service.init(token)
    with pytest.raises(UnauthorizedError):
        await harness.service.status(other_token, upload_id)


async def test_abort_discards_chunks_and_blocks_further_chunks(harness: Harness) -> None:
    content = png_bytes(150)
    upload_id, token = make_ticket(content)
    await harness.service.init(token)
    await harness.put(token, upload_id, content, 0)
    await harness.service.abort(token, upload_id)
    await harness.service.abort(token, upload_id)
    assert harness.chunks.received(upload_id) == set()
    with pytest.raises(ConflictError):
        await harness.put(token, upload_id, content, 1)
    with pytest.raises(ConflictError):
        await harness.service.init(token)


async def test_abort_after_complete_is_refused(harness: Harness) -> None:
    content = png_bytes(100)
    upload_id, token = make_ticket(content)
    await harness.service.init(token)
    await harness.put_all(token, upload_id, content)
    await harness.service.complete(token, upload_id)
    with pytest.raises(ConflictError):
        await harness.service.abort(token, upload_id)
