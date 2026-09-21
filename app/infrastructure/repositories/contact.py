from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Block, Contact
from app.domain.repositories.contact import BlockRepository, ContactRepository
from app.infrastructure.db.models import BlockModel, ContactModel


def contact_to_entity(model: ContactModel) -> Contact:
    return Contact(
        id=model.id,
        owner_id=model.owner_id,
        contact_id=model.contact_id,
        created_at=model.created_at,
    )


class SqlContactRepository(ContactRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entity_id: int) -> Contact | None:
        model = await self._session.get(ContactModel, entity_id)
        return contact_to_entity(model) if model else None

    async def get_pair(self, owner_id: int, contact_id: int) -> Contact | None:
        model = await self._session.scalar(
            select(ContactModel).where(
                ContactModel.owner_id == owner_id, ContactModel.contact_id == contact_id
            )
        )
        return contact_to_entity(model) if model else None

    async def list_by_owner(self, owner_id: int) -> list[Contact]:
        models = (
            await self._session.scalars(
                select(ContactModel)
                .where(ContactModel.owner_id == owner_id)
                .order_by(ContactModel.created_at.desc(), ContactModel.id.desc())
            )
        ).all()
        return [contact_to_entity(m) for m in models]

    async def add(self, entity: Contact) -> Contact:
        model = ContactModel(
            owner_id=entity.owner_id, contact_id=entity.contact_id, created_at=entity.created_at
        )
        self._session.add(model)
        await self._session.flush()
        return contact_to_entity(model)

    async def remove(self, owner_id: int, contact_id: int) -> None:
        await self._session.execute(
            delete(ContactModel).where(
                ContactModel.owner_id == owner_id, ContactModel.contact_id == contact_id
            )
        )
        await self._session.flush()

    async def delete(self, entity: Contact) -> None:
        await self.remove(entity.owner_id, entity.contact_id)


def block_to_entity(model: BlockModel) -> Block:
    return Block(
        id=model.id,
        blocker_id=model.blocker_id,
        blocked_id=model.blocked_id,
        created_at=model.created_at,
    )


class SqlBlockRepository(BlockRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entity_id: int) -> Block | None:
        model = await self._session.get(BlockModel, entity_id)
        return block_to_entity(model) if model else None

    async def get_pair(self, blocker_id: int, blocked_id: int) -> Block | None:
        model = await self._session.scalar(
            select(BlockModel).where(
                BlockModel.blocker_id == blocker_id, BlockModel.blocked_id == blocked_id
            )
        )
        return block_to_entity(model) if model else None

    async def list_by_blocker(self, blocker_id: int) -> list[Block]:
        models = (
            await self._session.scalars(
                select(BlockModel)
                .where(BlockModel.blocker_id == blocker_id)
                .order_by(BlockModel.created_at.desc(), BlockModel.id.desc())
            )
        ).all()
        return [block_to_entity(m) for m in models]

    async def blocks_either(self, user_a: int, user_b: int) -> bool:
        model = await self._session.scalar(
            select(BlockModel.id).where(
                or_(
                    (BlockModel.blocker_id == user_a) & (BlockModel.blocked_id == user_b),
                    (BlockModel.blocker_id == user_b) & (BlockModel.blocked_id == user_a),
                )
            )
        )
        return model is not None

    async def blockers_of(self, blocked_id: int) -> set[int]:
        ids = (
            await self._session.scalars(
                select(BlockModel.blocker_id).where(BlockModel.blocked_id == blocked_id)
            )
        ).all()
        return set(ids)

    async def add(self, entity: Block) -> Block:
        model = BlockModel(
            blocker_id=entity.blocker_id,
            blocked_id=entity.blocked_id,
            created_at=entity.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        return block_to_entity(model)

    async def remove(self, blocker_id: int, blocked_id: int) -> None:
        await self._session.execute(
            delete(BlockModel).where(
                BlockModel.blocker_id == blocker_id, BlockModel.blocked_id == blocked_id
            )
        )
        await self._session.flush()

    async def delete(self, entity: Block) -> None:
        await self.remove(entity.blocker_id, entity.blocked_id)
