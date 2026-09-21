from collections.abc import Sequence
from typing import Any, TypeVar

from app.domain.exceptions import ValidationError

T = TypeVar("T")

DEFAULT_LIMIT = 50
MAX_LIMIT = 100


def validate_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    if not 1 <= limit <= MAX_LIMIT:
        raise ValidationError(f"limit must be between 1 and {MAX_LIMIT}")
    return limit


def _item_id(item: Any) -> Any:
    return item["id"] if isinstance(item, dict) else item.id


def paginate_newest_first(items: Sequence[T], before_id: int | None, limit: int) -> list[T]:
    """Reference cursor pagination over items already sorted newest-first."""
    if before_id is None:
        return list(items[:limit])
    for index, item in enumerate(items):
        if _item_id(item) == before_id:
            return list(items[index + 1 : index + 1 + limit])
    raise ValidationError("before_id does not belong to this chat")
