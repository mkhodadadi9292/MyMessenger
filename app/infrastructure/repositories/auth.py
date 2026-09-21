from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import OtpCode, RefreshSession
from app.domain.repositories.auth import OtpRepository, RefreshSessionRepository
from app.infrastructure.db.models import OtpCodeModel, RefreshSessionModel


def otp_to_entity(model: OtpCodeModel) -> OtpCode:
    return OtpCode(
        id=model.id,
        identifier=model.identifier,
        code_hash=model.code_hash,
        purpose=model.purpose,
        expires_at=model.expires_at,
        used_at=model.used_at,
        created_at=model.created_at,
    )


class SqlOtpRepository(OtpRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entity_id: int) -> OtpCode | None:
        model = await self._session.get(OtpCodeModel, entity_id)
        return otp_to_entity(model) if model else None

    async def get_valid(self, identifier: str, code_hash: str, now: datetime) -> OtpCode | None:
        model = await self._session.scalar(
            select(OtpCodeModel)
            .where(
                OtpCodeModel.identifier == identifier,
                OtpCodeModel.code_hash == code_hash,
                OtpCodeModel.used_at.is_(None),
                OtpCodeModel.expires_at > now,
            )
            .order_by(OtpCodeModel.id.desc())
            .limit(1)
        )
        return otp_to_entity(model) if model else None

    async def mark_used(self, otp: OtpCode, now: datetime) -> None:
        model = await self._session.get(OtpCodeModel, otp.id)
        if model is not None:
            model.used_at = now
            await self._session.flush()

    async def add(self, entity: OtpCode) -> OtpCode:
        model = OtpCodeModel(
            identifier=entity.identifier,
            code_hash=entity.code_hash,
            purpose=entity.purpose,
            expires_at=entity.expires_at,
            used_at=entity.used_at,
            created_at=entity.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        return otp_to_entity(model)

    async def delete(self, entity: OtpCode) -> None:
        model = await self._session.get(OtpCodeModel, entity.id)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()


def session_to_entity(model: RefreshSessionModel) -> RefreshSession:
    return RefreshSession(
        id=model.id,
        user_id=model.user_id,
        token_hash=model.token_hash,
        expires_at=model.expires_at,
        revoked_at=model.revoked_at,
        created_at=model.created_at,
    )


class SqlRefreshSessionRepository(RefreshSessionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entity_id: int) -> RefreshSession | None:
        model = await self._session.get(RefreshSessionModel, entity_id)
        return session_to_entity(model) if model else None

    async def get_by_token_hash(self, token_hash: str) -> RefreshSession | None:
        model = await self._session.scalar(
            select(RefreshSessionModel).where(RefreshSessionModel.token_hash == token_hash)
        )
        return session_to_entity(model) if model else None

    async def revoke(self, session: RefreshSession, now: datetime) -> None:
        model = await self._session.get(RefreshSessionModel, session.id)
        if model is not None:
            model.revoked_at = now
            await self._session.flush()

    async def add(self, entity: RefreshSession) -> RefreshSession:
        model = RefreshSessionModel(
            user_id=entity.user_id,
            token_hash=entity.token_hash,
            expires_at=entity.expires_at,
            revoked_at=entity.revoked_at,
            created_at=entity.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        return session_to_entity(model)

    async def delete(self, entity: RefreshSession) -> None:
        model = await self._session.get(RefreshSessionModel, entity.id)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()
