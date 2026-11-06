import httpx
from core.interfaces.cleanup_api import ICleanupAPI
from settings import settings

class CleanupAPI(ICleanupAPI):
    def __init__(self):
        self.base_url = settings.file_service_url
        self.api_key = settings.cleanup_api_key

    async def cleanup(self, session_id: str) -> None:
        url = f"{self.base_url}/internal/cleanup/{session_id}"
        async with httpx.AsyncClient() as client:
            await client.post(
                url,
                headers={"x-api-key": self.api_key},
            )

    async def delete(self, session_id: str) -> None:
        url = f"{self.base_url}/internal/cleanup/file/{session_id}"
        async with httpx.AsyncClient() as client:
            await client.post(
                url,
                headers={"x-api-key": self.api_key},
            )
