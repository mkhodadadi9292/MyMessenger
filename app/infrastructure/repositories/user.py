from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import User
from app.domain.repositories.user import UserRepository
from app.domain.value_objects import Phone, Username
from app.infrastructure.db.models import UserModel


def user_to_entity(model: UserModel) -> User:
    return User(
        id=model.id,
        username=Username(model.username),
        phone=Phone(model.phone) if model.phone else None,
        email=model.email,
        first_name=model.first_name,
        last_name=model.last_name,
        bio=model.bio,
        avatar_path=model.avatar_path,
        created_at=model.created_at,
    )


def user_to_model(entity: User) -> UserModel:
    return UserModel(
        id=entity.id or None,
        username=str(entity.username),
        phone=str(entity.phone) if entity.phone else None,
        email=entity.email,
        first_name=entity.first_name,
        last_name=entity.last_name,
        bio=entity.bio,
        avatar_path=entity.avatar_path,
        created_at=entity.created_at,
    )


class SqlUserRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entity_id: int) -> User | None:
        model = await self._session.get(UserModel, entity_id)
        return user_to_entity(model) if model else None

    async def get_by_username(self, username: str) -> User | None:
        model = await self._session.scalar(
            select(UserModel).where(UserModel.username == username)
        )
        return user_to_entity(model) if model else None

    async def get_by_identifier(self, identifier: str) -> User | None:
        model = await self._session.scalar(
            select(UserModel).where(
                (UserModel.email == identifier) | (UserModel.phone == identifier)
            )
        )
        return user_to_entity(model) if model else None

    async def list_by_ids(self, user_ids: Sequence[int]) -> list[User]:
        if not user_ids:
            return []
        models = (
            await self._session.scalars(
                select(UserModel).where(UserModel.id.in_(list(user_ids)))
            )
        ).all()
        return [user_to_entity(m) for m in models]

    async def search(self, query: str) -> list[User]:
        if query.startswith("+"):
            stmt = select(UserModel).where(UserModel.phone == query)
        else:
            stmt = select(UserModel).where(UserModel.username.startswith(query))
        models = (await self._session.scalars(stmt)).all()
        return [user_to_entity(m) for m in models]

    async def add(self, entity: User) -> User:
        model = user_to_model(entity)
        self._session.add(model)
        await self._session.flush()
        return user_to_entity(model)

    async def update(self, entity: User) -> User:
        model = await self._session.get(UserModel, entity.id)
        if model is None:
            return await self.add(entity)
        model.username = str(entity.username)
        model.phone = str(entity.phone) if entity.phone else None
        model.email = entity.email
        model.first_name = entity.first_name
        model.last_name = entity.last_name
        model.bio = entity.bio
        model.avatar_path = entity.avatar_path
        await self._session.flush()
        return user_to_entity(model)

    async def delete(self, entity: User) -> None:
        model = await self._session.get(UserModel, entity.id)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()
