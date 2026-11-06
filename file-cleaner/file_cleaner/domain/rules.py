from dataclasses import dataclass
from enum import StrEnum


class CleanupRule(StrEnum):
    STALE_ACTIVE = "stale-active"
    STUCK_ASSEMBLING = "stuck-assembling"
    UNATTACHED = "unattached"
    TERMINAL = "terminal"
    ORPHAN_CHUNK_DIRS = "orphan-chunk-dirs"


@dataclass(frozen=True)
class RulePolicy:
    rule: CleanupRule
    older_than_seconds: int
    interval_seconds: int


@dataclass(frozen=True)
class CleanupReport:
    rule: CleanupRule
    purged: list[str]
    skipped: list[str]


class UnsafeCleanupPolicyError(ValueError):
    pass


def validate_attach_grace(attach_grace_seconds: int, backend_event_max_age_seconds: int) -> None:
    if attach_grace_seconds <= backend_event_max_age_seconds:
        raise UnsafeCleanupPolicyError(
            "ATTACH_GRACE_PERIOD_SECONDS must be longer than the backend's "
            "UPLOAD_EVENT_MAX_AGE_SECONDS, otherwise a late attach could hit a deleted file"
        )
