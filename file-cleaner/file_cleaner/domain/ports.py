from abc import ABC, abstractmethod

from file_cleaner.domain.rules import CleanupReport, CleanupRule


class CleanupApi(ABC):
    @abstractmethod
    async def run(self, rule: CleanupRule, older_than_seconds: int, limit: int) -> CleanupReport:
        ...
