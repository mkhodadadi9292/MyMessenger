from app.domain.entities import Block, User
from app.domain.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.repositories.contact import BlockRepository
from app.domain.repositories.user import UserRepository
from app.domain.time import utcnow


class BlockService:
    def __init__(self, blocks: BlockRepository, users: UserRepository) -> None:
        self._blocks = blocks
        self._users = users

    async def list_blocked(self, blocker_id: int) -> list[tuple[Block, User]]:
        entries = await self._blocks.list_by_blocker(blocker_id)
        users = await self._users.list_by_ids([e.blocked_id for e in entries])
        by_id = {u.id: u for u in users}
        return [(e, by_id[e.blocked_id]) for e in entries if e.blocked_id in by_id]

    async def block(self, blocker_id: int, blocked_id: int) -> None:
        if blocker_id == blocked_id:
            raise ValidationError("cannot block yourself")
        target = await self._users.get(blocked_id)
        if target is None:
            raise NotFoundError("user not found")
        if await self._blocks.get_pair(blocker_id, blocked_id) is not None:
            raise ConflictError("user is already blocked")
        block = Block(id=0, blocker_id=blocker_id, blocked_id=blocked_id, created_at=utcnow())
        await self._blocks.add(block)

    async def unblock(self, blocker_id: int, blocked_id: int) -> None:
        if await self._blocks.get_pair(blocker_id, blocked_id) is None:
            raise NotFoundError("user is not blocked")
        await self._blocks.remove(blocker_id, blocked_id)
