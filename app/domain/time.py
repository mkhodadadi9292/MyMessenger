from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC now — stored values in SQLite are naive."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
