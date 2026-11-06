import asyncio
import logging

from file_cleaner.domain.ports import CleanupApi
from file_cleaner.domain.rules import CleanupReport, RulePolicy

logger = logging.getLogger("file_cleaner")


class CleanupScheduler:
    def __init__(self, api: CleanupApi, policies: list[RulePolicy], batch_limit: int) -> None:
        self._api = api
        self._policies = policies
        self._batch_limit = batch_limit
        self._next_run: dict[RulePolicy, float] = {policy: 0.0 for policy in policies}

    async def run_due(self, now: float) -> list[CleanupReport]:
        reports: list[CleanupReport] = []
        for policy in self._policies:
            if now < self._next_run[policy]:
                continue
            self._next_run[policy] = now + policy.interval_seconds
            try:
                report = await self._api.run(
                    policy.rule, policy.older_than_seconds, self._batch_limit
                )
            except Exception:
                logger.exception("cleanup rule %s failed; nothing deleted this round", policy.rule)
                continue
            if report.purged:
                logger.info("rule %s purged %d uploads", policy.rule, len(report.purged))
            reports.append(report)
        return reports

    def seconds_until_next_run(self, now: float) -> float:
        return max(0.0, min(self._next_run.values()) - now)

    async def run_forever(self, stop: asyncio.Event) -> None:
        loop = asyncio.get_running_loop()
        while not stop.is_set():
            await self.run_due(loop.time())
            wait = self.seconds_until_next_run(loop.time())
            try:
                await asyncio.wait_for(stop.wait(), timeout=max(wait, 1.0))
            except TimeoutError:
                pass
