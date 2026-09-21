from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_contact_service, get_current_user
from app.api.schemas.common import contact_to_out
from app.application.contact_service import ContactService
from app.domain.entities import User

router = APIRouter(prefix="/contacts", tags=["contacts"])


class ContactAddIn(BaseModel):
    identifier: str


class ContactRenameIn(BaseModel):
    name: str | None = None


@router.get("")
async def list_contacts(
    current_user: User = Depends(get_current_user),
    service: ContactService = Depends(get_contact_service),
) -> list[dict]:
    entries = await service.list_contacts(current_user.id)
    return [contact_to_out(user, contact.name).model_dump() for contact, user in entries]


@router.post("")
async def add_contact(
    body: ContactAddIn,
    current_user: User = Depends(get_current_user),
    service: ContactService = Depends(get_contact_service),
) -> dict:
    _, user = await service.add_contact(current_user.id, body.identifier)
    return contact_to_out(user).model_dump()


@router.patch("/{user_id}")
async def rename_contact(
    user_id: int,
    body: ContactRenameIn,
    current_user: User = Depends(get_current_user),
    service: ContactService = Depends(get_contact_service),
) -> dict:
    contact, user = await service.rename_contact(current_user.id, user_id, body.name)
    return contact_to_out(user, contact.name).model_dump()


@router.delete("/{user_id}")
async def remove_contact(
    user_id: int,
    current_user: User = Depends(get_current_user),
    service: ContactService = Depends(get_contact_service),
) -> dict:
    await service.remove_contact(current_user.id, user_id)
    return {"ok": True}
