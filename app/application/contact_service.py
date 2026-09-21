from app.domain.entities import Contact, User
from app.domain.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.domain.repositories.contact import BlockRepository, ContactRepository
from app.domain.repositories.user import UserRepository
from app.domain.time import utcnow


class ContactService:
    def __init__(
        self,
        contacts: ContactRepository,
        users: UserRepository,
        blocks: BlockRepository,
    ) -> None:
        self._contacts = contacts
        self._users = users
        self._blocks = blocks

    async def _resolve(self, identifier: str) -> User:
        if identifier.startswith("+"):
            user = await self._users.get_by_identifier(identifier)
        else:
            user = await self._users.get_by_username(identifier)
        if user is None:
            raise NotFoundError("user not found")
        return user

    async def list_contacts(self, owner_id: int) -> list[tuple[Contact, User]]:
        entries = await self._contacts.list_by_owner(owner_id)
        users = await self._users.list_by_ids([e.contact_id for e in entries])
        by_id = {u.id: u for u in users}
        return [(e, by_id[e.contact_id]) for e in entries if e.contact_id in by_id]

    async def add_contact(self, owner_id: int, identifier: str) -> tuple[Contact, User]:
        target = await self._resolve(identifier)
        if target.id == owner_id:
            raise ValidationError("cannot add yourself to contacts")
        if await self._blocks.blocks_either(owner_id, target.id):
            raise ForbiddenError("cannot add this user to contacts")
        if await self._contacts.get_pair(owner_id, target.id) is not None:
            raise ConflictError("contact already exists")
        contact = Contact(id=0, owner_id=owner_id, contact_id=target.id, created_at=utcnow())
        created = await self._contacts.add(contact)
        return created, target

    async def remove_contact(self, owner_id: int, contact_id: int) -> None:
        if await self._contacts.get_pair(owner_id, contact_id) is None:
            raise NotFoundError("contact not found")
        await self._contacts.remove(owner_id, contact_id)

    async def rename_contact(
        self, owner_id: int, contact_id: int, name: str | None
    ) -> tuple[Contact, User]:
        contact = await self._contacts.get_pair(owner_id, contact_id)
        if contact is None:
            raise NotFoundError("contact not found")
        if name is not None:
            name = name.strip()
            if not name:
                raise ValidationError("contact name cannot be empty")
            if len(name) > 64:
                raise ValidationError("contact name is too long")
        updated = await self._contacts.rename(owner_id, contact_id, name)
        target = await self._users.get(contact_id)
        if target is None:
            raise NotFoundError("user not found")
        return updated, target
