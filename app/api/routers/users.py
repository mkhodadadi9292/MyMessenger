from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel

from app.api.deps import get_current_user, get_user_service
from app.api.schemas.common import user_to_public
from app.application.user_service import UserService
from app.domain.entities import User

router = APIRouter(prefix="/users", tags=["users"])


class UserUpdateIn(BaseModel):
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    bio: str | None = None


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> dict:
    user = await service.get_me(current_user.id)
    return user_to_public(user).model_dump()


@router.patch("/me")
async def update_me(
    body: UserUpdateIn,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> dict:
    user = await service.update_me(
        current_user.id,
        username=body.username,
        first_name=body.first_name,
        last_name=body.last_name,
        bio=body.bio,
    )
    return user_to_public(user).model_dump()


@router.get("/search")
async def search_users(
    q: str,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> list[dict]:
    users = await service.search(current_user.id, q)
    return [user_to_public(u).model_dump() for u in users]


@router.get("/{user_id}")
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> dict:
    user = await service.get_public_profile(current_user.id, user_id)
    return user_to_public(user).model_dump()


@router.post("/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> dict:
    content = await file.read()
    user = await service.upload_avatar(current_user.id, file.filename or "avatar", file.content_type or "", content)
    return user_to_public(user).model_dump()
