from utility.session_id import generate_session_id
from core.interfaces.store import IStore

class StartUploadUseCase:
    def __init__(self, store: IStore):
        self.store = store

    async def execute(self, public_id: str) -> str:
        session_id = generate_session_id()

        await self.store.init_session(session_id,public_id)

        return session_id

