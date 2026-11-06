from datetime import UTC, datetime

from file_service.domain.ports import Clock


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SystemClock(Clock):
    def now(self) -> datetime:
        return utcnow()
