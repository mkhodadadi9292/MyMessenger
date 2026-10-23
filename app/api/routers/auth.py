from fastapi import APIRouter, Depends
from pydantic import BaseModel

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_auth_service,
    get_db,
    get_otp_sender,
    get_settings,
)
from app.api.schemas.common import user_to_public
from app.application.auth_service import AuthService
from app.application.ports import OtpSender
from app.config import Settings
from app.domain.exceptions import ForbiddenError, NotFoundError

router = APIRouter(prefix="/auth", tags=["auth"])


class OtpRequestIn(BaseModel):
    identifier: str


class OtpVerifyIn(BaseModel):
    identifier: str
    code: str


class RegisterIn(BaseModel):
    registration_token: str
    username: str
    first_name: str
    last_name: str | None = None


class RefreshIn(BaseModel):
    refresh_token: str


def _token_response(result: dict) -> dict:
    return {
        "access_token": result["access_token"],
        "refresh_token": result["refresh_token"],
        "user": user_to_public(result["user"]).model_dump(),
    }


@router.post("/otp/request")
async def request_otp(
    body: OtpRequestIn,
    service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await service.request_otp(body.identifier)
    # commit before the response so an immediate /otp/verify sees the code
    await db.commit()
    return result


@router.post("/otp/verify")
async def verify_otp(
    body: OtpVerifyIn,
    service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await service.verify_otp(body.identifier, body.code)
    await db.commit()
    if result.get("registered") is False:
        return result
    return _token_response(result)


@router.post("/register")
async def register(
    body: RegisterIn,
    service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await service.register(
        body.registration_token, body.username, body.first_name, body.last_name
    )
    # commit before the response so other users can immediately find/search
    # the new account (read-committed visibility)
    await db.commit()
    return _token_response(result)


@router.get("/otp/dev/latest")
async def dev_latest_otp(
    identifier: str,
    settings: Settings = Depends(get_settings),
    sender: OtpSender = Depends(get_otp_sender),
) -> dict:
    """Dev-only helper: returns the last OTP sent for an identifier (debug mode)."""
    if not settings.debug:
        raise ForbiddenError("dev otp endpoint is disabled")
    code = getattr(sender, "last_codes", {}).get(identifier)
    if code is None:
        raise NotFoundError("no otp requested for this identifier")
    return {"code": code}


@router.post("/refresh")
async def refresh(body: RefreshIn, service: AuthService = Depends(get_auth_service)) -> dict:
    result = await service.refresh(body.refresh_token)
    return {"access_token": result["access_token"], "refresh_token": result["refresh_token"]}


@router.post("/logout")
async def logout(body: RefreshIn, service: AuthService = Depends(get_auth_service)) -> dict:
    await service.logout(body.refresh_token)
    return {"ok": True}
