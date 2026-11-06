import httpx

from file_cleaner.domain.ports import CleanupApi
from file_cleaner.domain.rules import CleanupReport, CleanupRule


class HttpCleanupApi(CleanupApi):
    def __init__(self, client: httpx.AsyncClient, internal_api_key: str) -> None:
        self._client = client
        self._internal_api_key = internal_api_key

    async def run(self, rule: CleanupRule, older_than_seconds: int, limit: int) -> CleanupReport:
        response = await self._client.post(
            f"/internal/v1/cleanup/{rule.value}",
            json={"older_than_seconds": older_than_seconds, "limit": limit},
            headers={"X-Internal-Key": self._internal_api_key},
        )
        response.raise_for_status()
        body = response.json()
        return CleanupReport(rule=rule, purged=body["purged"], skipped=body["skipped"])
