import pytest

from file_service.domain.exceptions import UnauthorizedError
from file_service.infrastructure.tickets import JwtTicketVerifier
from tests.helpers import TEST_AUDIENCE, TEST_ISSUER, TEST_TICKET_SECRET, make_ticket, png_bytes

CONTENT = png_bytes(100)


def verifier() -> JwtTicketVerifier:
    return JwtTicketVerifier(TEST_TICKET_SECRET, TEST_ISSUER, TEST_AUDIENCE)


def test_valid_ticket_yields_claims() -> None:
    upload_id, token = make_ticket(CONTENT, user_id=7)
    ticket = verifier().verify(token)
    assert ticket.upload_id == upload_id
    assert ticket.user_id == 7
    assert ticket.size_bytes == len(CONTENT)
    assert ticket.raw == token


def test_expired_ticket_is_rejected() -> None:
    _, token = make_ticket(CONTENT, ttl_seconds=-5)
    with pytest.raises(UnauthorizedError, match="expired"):
        verifier().verify(token)


def test_tampered_ticket_is_rejected() -> None:
    _, token = make_ticket(CONTENT)
    header, payload, signature = token.split(".")
    tampered = f"{header}.{payload[:-2]}AA.{signature}"
    with pytest.raises(UnauthorizedError):
        verifier().verify(tampered)


def test_ticket_signed_with_other_secret_is_rejected() -> None:
    _, token = make_ticket(CONTENT, secret="another-secret-0123456789-0123456789-xx")
    with pytest.raises(UnauthorizedError):
        verifier().verify(token)


@pytest.mark.parametrize(
    "overrides",
    [{"audience": "someone-else"}, {"issuer": "someone-else"}, {"typ": "access"}],
)
def test_wrong_audience_issuer_or_type_is_rejected(overrides: dict) -> None:
    _, token = make_ticket(CONTENT, **overrides)
    with pytest.raises(UnauthorizedError):
        verifier().verify(token)


def test_ticket_is_bound_to_its_upload() -> None:
    _, token = make_ticket(CONTENT)
    with pytest.raises(UnauthorizedError):
        verifier().verify(token).require_upload("0" * 32)
