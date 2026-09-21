from abc import abstractmethod
from datetime import datetime

from app.domain.entities import OtpCode, RefreshSession
from app.domain.repositories.base import AbstractRepository


class OtpRepository(AbstractRepository[OtpCode, int]):
    @abstractmethod
    async def get_valid(self, identifier: str, code_hash: str, now: datetime) -> OtpCode | None:
        ...

    @abstractmethod
    async def mark_used(self, otp: OtpCode, now: datetime) -> None:
        ...


class RefreshSessionRepository(AbstractRepository[RefreshSession, int]):
    @abstractmethod
    async def get_by_token_hash(self, token_hash: str) -> RefreshSession | None:
        ...

    @abstractmethod
    async def revoke(self, session: RefreshSession, now: datetime) -> None:
        ...
