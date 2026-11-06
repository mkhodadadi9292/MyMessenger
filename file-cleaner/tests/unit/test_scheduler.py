import httpx
import pytest

from file_cleaner.application.scheduler import CleanupScheduler
from file_cleaner.config import Settings
from file_cleaner.domain.ports import CleanupApi
from file_cleaner.domain.rules import (
    CleanupReport,
    CleanupRule,
    RulePolicy,
    UnsafeCleanupPolicyError,
)
from file_cleaner.infrastructure.http_api import HttpCleanupApi


class RecordingApi(CleanupApi):
    def __init__(self, failing: set[CleanupRule] | None = None) -> None:
        self.calls: list[tuple[CleanupRule, int, int]] = []
        self.failing = failing or set()

    async def run(self, rule: CleanupRule, older_than_seconds: int, limit: int) -> CleanupReport:
        self.calls.append((rule, older_than_seconds, limit))
        if rule in self.failing:
            raise httpx.ConnectError("file-service down")
        return CleanupReport(rule, purged=[], skipped=[])


def test_default_policy_covers_every_rule_with_configured_thresholds() -> None:
    settings = Settings(
        _env_file=None, upload_session_ttl_seconds=111, attach_grace_period_seconds=99_999
    )
    policies = {p.rule: p for p in settings.policies()}
    assert set(policies) == set(CleanupRule)
    assert policies[CleanupRule.STALE_ACTIVE].older_than_seconds == 111
    assert policies[CleanupRule.UNATTACHED].older_than_seconds == 99_999


def test_attach_grace_must_exceed_backend_event_max_age() -> None:
    settings = Settings(
        _env_file=None,
        attach_grace_period_seconds=3600,
        backend_upload_event_max_age_seconds=3600,
    )
    with pytest.raises(UnsafeCleanupPolicyError):
        settings.policies()


async def test_each_rule_runs_with_its_threshold_and_batch_limit() -> None:
    api = RecordingApi()
    policies = [RulePolicy(rule, 10 * i + 1, 60) for i, rule in enumerate(CleanupRule)]
    await CleanupScheduler(api, policies, batch_limit=7).run_due(now=0)
    assert api.calls == [(p.rule, p.older_than_seconds, 7) for p in policies]


async def test_rules_respect_their_own_intervals() -> None:
    api = RecordingApi()
    fast = RulePolicy(CleanupRule.TERMINAL, 0, 10)
    slow = RulePolicy(CleanupRule.UNATTACHED, 0, 100)
    scheduler = CleanupScheduler(api, [fast, slow], batch_limit=1)
    await scheduler.run_due(now=0)
    await scheduler.run_due(now=5)
    await scheduler.run_due(now=10)
    await scheduler.run_due(now=50)
    rules = [rule for rule, _, _ in api.calls]
    assert rules == [
        CleanupRule.TERMINAL, CleanupRule.UNATTACHED, CleanupRule.TERMINAL, CleanupRule.TERMINAL
    ]
    assert scheduler.seconds_until_next_run(now=50) == 10


async def test_failure_of_one_rule_does_not_stop_the_others() -> None:
    api = RecordingApi(failing={CleanupRule.STALE_ACTIVE})
    policies = [
        RulePolicy(CleanupRule.STALE_ACTIVE, 1, 60),
        RulePolicy(CleanupRule.TERMINAL, 1, 60),
    ]
    reports = await CleanupScheduler(api, policies, batch_limit=1).run_due(now=0)
    assert [r.rule for r in reports] == [CleanupRule.TERMINAL]
    assert len(api.calls) == 2


async def test_http_api_sends_rule_threshold_and_internal_key() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"rule": "terminal", "purged": ["a"], "skipped": []})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://fs"
    ) as client:
        report = await HttpCleanupApi(client, "secret-key").run(CleanupRule.TERMINAL, 600, 50)
    assert report.purged == ["a"]
    assert seen[0].url.path == "/internal/v1/cleanup/terminal"
    assert seen[0].headers["X-Internal-Key"] == "secret-key"
    assert seen[0].read() == b'{"older_than_seconds":600,"limit":50}'


async def test_http_errors_surface_so_nothing_is_assumed_deleted() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(503)), base_url="http://fs"
    ) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await HttpCleanupApi(client, "k").run(CleanupRule.TERMINAL, 1, 1)
