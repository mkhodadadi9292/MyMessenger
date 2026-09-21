from datetime import datetime, timedelta, timezone

import jwt

from app.config import Settings
from app.domain.exceptions import UnauthorizedError

TOKEN_ACCESS = "access"
TOKEN_REFRESH = "refresh"
TOKEN_REGISTRATION = "registration"


def _create_token(sub: str, token_type: str, ttl: timedelta, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": sub, "type": token_type, "iat": now, "exp": now + ttl}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: int, settings: Settings) -> str:
    return _create_token(
        str(user_id), TOKEN_ACCESS, timedelta(minutes=settings.access_token_ttl_minutes), settings
    )


def create_refresh_token(user_id: int, settings: Settings) -> str:
    return _create_token(
        str(user_id), TOKEN_REFRESH, timedelta(days=settings.refresh_token_ttl_days), settings
    )


def create_registration_token(identifier: str, settings: Settings) -> str:
    return _create_token(
        identifier,
        TOKEN_REGISTRATION,
        timedelta(minutes=settings.registration_token_ttl_minutes),
        settings,
    )


def decode_token(token: str, settings: Settings) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("invalid or expired token") from exc
