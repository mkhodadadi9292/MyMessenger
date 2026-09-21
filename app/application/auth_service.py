import re
from datetime import timedelta

from app.application.ports import OtpSender
from app.config import Settings
from app.domain.entities import OtpCode, RefreshSession, User
from app.domain.exceptions import ConflictError, UnauthorizedError, ValidationError
from app.domain.repositories.auth import OtpRepository, RefreshSessionRepository
from app.domain.repositories.user import UserRepository
from app.domain.time import utcnow
from app.domain.value_objects import Phone, Username
from app.infrastructure.auth.jwt import (
    TOKEN_REGISTRATION,
    TOKEN_REFRESH,
    create_access_token,
    create_refresh_token,
    create_registration_token,
    decode_token,
)
from app.infrastructure.auth.otp import generate_code, hash_code, sha256_hex

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_identifier(identifier: str) -> str:
    value = identifier.strip()
    if "@" in value:
        value = value.lower()
    return value


class AuthService:
    def __init__(
        self,
        users: UserRepository,
        otps: OtpRepository,
        sessions: RefreshSessionRepository,
        sender: OtpSender,
        settings: Settings,
    ) -> None:
        self._users = users
        self._otps = otps
        self._sessions = sessions
        self._sender = sender
        self._settings = settings

    def _validate_identifier(self, identifier: str) -> None:
        if "@" in identifier:
            if not _EMAIL_RE.fullmatch(identifier):
                raise ValidationError("invalid email address")
        else:
            Phone(identifier)

    async def request_otp(self, identifier: str) -> dict:
        identifier = normalize_identifier(identifier)
        self._validate_identifier(identifier)
        now = utcnow()
        code = generate_code(self._settings.otp_length)
        existing = await self._users.get_by_identifier(identifier)
        otp = OtpCode(
            id=0,
            identifier=identifier,
            code_hash=hash_code(code),
            purpose="login" if existing else "register",
            expires_at=now + timedelta(seconds=self._settings.otp_ttl_seconds),
            used_at=None,
            created_at=now,
        )
        saved = await self._otps.add(otp)
        await self._sender.send(identifier, code)
        return {"otp_id": saved.id, "expires_in": self._settings.otp_ttl_seconds, "delivery": "log"}

    async def verify_otp(self, identifier: str, code: str) -> dict:
        identifier = normalize_identifier(identifier)
        otp = await self._otps.get_valid(identifier, hash_code(code), utcnow())
        if otp is None:
            raise ValidationError("invalid or expired otp code")
        await self._otps.mark_used(otp, utcnow())
        user = await self._users.get_by_identifier(identifier)
        if user is None:
            return {
                "registered": False,
                "registration_token": create_registration_token(identifier, self._settings),
            }
        return await self._issue_tokens(user)

    async def register(
        self,
        registration_token: str,
        username: str,
        first_name: str,
        last_name: str | None,
    ) -> dict:
        try:
            payload = decode_token(registration_token, self._settings)
        except UnauthorizedError as exc:
            raise ValidationError("invalid registration token") from exc
        if payload.get("type") != TOKEN_REGISTRATION:
            raise ValidationError("invalid registration token")
        identifier = payload["sub"]
        if await self._users.get_by_identifier(identifier) is not None:
            raise ConflictError("user with this identifier is already registered")
        username_vo = Username(username)
        if await self._users.get_by_username(str(username_vo)) is not None:
            raise ConflictError("username is already taken")
        is_email = "@" in identifier
        user = User(
            id=0,
            username=username_vo,
            phone=None if is_email else Phone(identifier),
            email=identifier if is_email else None,
            first_name=first_name,
            last_name=last_name,
            bio=None,
            avatar_path=None,
            created_at=utcnow(),
        )
        created = await self._users.add(user)
        return await self._issue_tokens(created)

    async def refresh(self, refresh_token: str) -> dict:
        try:
            payload = decode_token(refresh_token, self._settings)
        except UnauthorizedError:
            raise
        if payload.get("type") != TOKEN_REFRESH:
            raise UnauthorizedError("invalid refresh token")
        now = utcnow()
        session = await self._sessions.get_by_token_hash(sha256_hex(refresh_token))
        if session is None or session.revoked_at is not None or now >= session.expires_at:
            raise UnauthorizedError("refresh token revoked or expired")
        user = await self._users.get(session.user_id)
        if user is None:
            raise UnauthorizedError("user not found")
        await self._sessions.revoke(session, now)
        return await self._issue_tokens(user)

    async def logout(self, refresh_token: str) -> None:
        try:
            payload = decode_token(refresh_token, self._settings)
        except UnauthorizedError:
            raise
        if payload.get("type") != TOKEN_REFRESH:
            raise UnauthorizedError("invalid refresh token")
        session = await self._sessions.get_by_token_hash(sha256_hex(refresh_token))
        if session is None:
            raise UnauthorizedError("unknown refresh token")
        if session.revoked_at is None:
            await self._sessions.revoke(session, utcnow())

    async def _issue_tokens(self, user: User) -> dict:
        now = utcnow()
        access = create_access_token(user.id, self._settings)
        refresh = create_refresh_token(user.id, self._settings)
        session = RefreshSession(
            id=0,
            user_id=user.id,
            token_hash=sha256_hex(refresh),
            expires_at=now + timedelta(days=self._settings.refresh_token_ttl_days),
            revoked_at=None,
            created_at=now,
        )
        await self._sessions.add(session)
        return {"access_token": access, "refresh_token": refresh, "user": user}
