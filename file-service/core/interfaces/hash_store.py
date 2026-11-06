from typing import Optional


class IHashStateStore:
    async def set_state(self, session_id: str, state: str) -> None:
        raise NotImplementedError

    async def get_state(self, session_id: str) -> Optional[str]:
        raise NotImplementedError

    async def delete_state(self, session_id: str) -> None:
        raise NotImplementedError