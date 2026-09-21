import pytest

from app.config import Settings
from app.domain.exceptions import UnauthorizedError
from app.infrastructure.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
)


@pytest.fixture
def settings() -> Settings:
    return Settings(jwt_secret="test-secret-0123456789-0123456789", _env_file=None)


def test_access_token_roundtrip(settings: Settings) -> None:
    payload = decode_token(create_access_token(42, settings), settings)
    assert payload["sub"] == "42"


def test_token_type_marker(settings: Settings) -> None:
    assert decode_token(create_access_token(1, settings), settings)["type"] == "access"
    assert decode_token(create_refresh_token(1, settings), settings)["type"] == "refresh"


def test_decode_with_wrong_secret(settings: Settings) -> None:
    token = create_access_token(1, settings)
    other = Settings(jwt_secret="other-test-secret-0123456789-0123456789", _env_file=None)
    with pytest.raises(UnauthorizedError):
        decode_token(token, other)


def test_expired_access_token(settings: Settings) -> None:
    expired_settings = settings.model_copy(update={"access_token_ttl_minutes": -1})
    with pytest.raises(UnauthorizedError):
        decode_token(create_access_token(1, expired_settings), expired_settings)


def test_expired_refresh_token(settings: Settings) -> None:
    expired_settings = settings.model_copy(update={"refresh_token_ttl_days": -1})
    with pytest.raises(UnauthorizedError):
        decode_token(create_refresh_token(1, expired_settings), expired_settings)


@pytest.mark.parametrize("token", ["", "not-a-jwt", "a.b.c"])
def test_malformed_token(settings: Settings, token: str) -> None:
    with pytest.raises(UnauthorizedError):
        decode_token(token, settings)
