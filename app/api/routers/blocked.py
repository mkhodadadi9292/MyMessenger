from fastapi import APIRouter, Depends

from app.api.deps import get_block_service, get_current_user
from app.api.schemas.common import contact_to_out
from app.application.block_service import BlockService
from app.domain.entities import User

router = APIRouter(prefix="/blocked", tags=["blocked"])


@router.get("")
async def list_blocked(
    current_user: User = Depends(get_current_user),
    service: BlockService = Depends(get_block_service),
) -> list[dict]:
    entries = await service.list_blocked(current_user.id)
    return [contact_to_out(user).model_dump() for _, user in entries]


@router.post("/{user_id}")
async def block_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    service: BlockService = Depends(get_block_service),
) -> dict:
    await service.block(current_user.id, user_id)
    return {"ok": True}


@router.delete("/{user_id}")
async def unblock_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    service: BlockService = Depends(get_block_service),
) -> dict:
    await service.unblock(current_user.id, user_id)
    return {"ok": True}
