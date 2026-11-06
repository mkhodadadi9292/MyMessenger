import hmac
from collections.abc import AsyncIterator

from fastapi import Depends, Header, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from file_service.application.cleanup_service import CleanupService
from file_service.application.upload_service import UploadService
from file_service.config import Settings
from file_service.domain.exceptions import UnauthorizedError
from file_service.infrastructure.composition import build_cleanup_service, build_upload_service


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_redis(request: Request) -> Redis | None:
    return request.app.state.redis


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_ticket(authorization: str | None = Header(default=None)) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise UnauthorizedError("missing upload ticket")
    return token


def require_internal_key(
    request: Request, x_internal_key: str | None = Header(default=None)
) -> None:
    expected = request.app.state.settings.internal_api_key
    if not x_internal_key or not hmac.compare_digest(x_internal_key, expected):
        raise UnauthorizedError("invalid internal key")


def get_upload_service(
    db: AsyncSession = Depends(get_db),
    redis: Redis | None = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> UploadService:
    return build_upload_service(db, redis, settings)


def get_cleanup_service(
    db: AsyncSession = Depends(get_db),
    redis: Redis | None = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> CleanupService:
    if redis is None:
        raise UnauthorizedError("cleanup needs redis")
    return build_cleanup_service(db, redis, settings)
