from app.config import Settings
from app.domain.entities import User
from app.domain.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.domain.repositories.contact import BlockRepository
from app.domain.repositories.user import UserRepository
from app.domain.value_objects import Username
from app.infrastructure.storage import LocalStorage


class UserService:
    def __init__(
        self,
        users: UserRepository,
        blocks: BlockRepository,
        storage: LocalStorage,
        settings: Settings,
    ) -> None:
        self._users = users
        self._blocks = blocks
        self._storage = storage
        self._settings = settings

    async def get_me(self, user_id: int) -> User:
        user = await self._users.get(user_id)
        if user is None:
            raise NotFoundError("user not found")
        return user

    async def update_me(
        self,
        user_id: int,
        *,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        bio: str | None = None,
    ) -> User:
        user = await self.get_me(user_id)
        if username is not None:
            username_vo = Username(username)
            if str(username_vo) != str(user.username):
                if await self._users.get_by_username(str(username_vo)) is not None:
                    raise ConflictError("username is already taken")
                user.username = username_vo
        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name
        if bio is not None:
            user.bio = bio
        return await self._users.update(user)

    async def get_public_profile(self, viewer_id: int, target_id: int) -> User:
        target = await self._users.get(target_id)
        if target is None:
            raise NotFoundError("user not found")
        if await self._blocks.blocks_either(viewer_id, target_id):
            raise ForbiddenError("profile is hidden")
        return target

    async def search(self, viewer_id: int, query: str) -> list[User]:
        query = query.strip()
        if not query:
            return []
        candidates = await self._users.search(query)
        if not candidates:
            return []
        blocked = await self._blocks.list_by_blocker(viewer_id)
        blockers = await self._blocks.blockers_of(viewer_id)
        excluded = {b.blocked_id for b in blocked} | blockers
        return [u for u in candidates if u.id not in excluded and u.id != viewer_id]

    async def upload_avatar(
        self, user_id: int, file_name: str, mime_type: str, content: bytes
    ) -> User:
        if not mime_type.startswith("image/"):
            raise ValidationError("avatar must be an image")
        max_bytes = self._settings.max_artifact_size_mb * 1024 * 1024
        if len(content) > max_bytes:
            raise ValidationError("avatar is too large")
        user = await self.get_me(user_id)
        relative = self._storage.save("avatars", file_name, content)
        user.avatar_path = relative
        return await self._users.update(user)
