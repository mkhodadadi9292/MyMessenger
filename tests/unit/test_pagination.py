import pytest

from app.domain.exceptions import ValidationError
from app.domain.pagination import paginate_newest_first, validate_limit

ITEMS = [{"id": 10}, {"id": 9}, {"id": 8}, {"id": 7}, {"id": 6}]


def test_validate_limit_default() -> None:
    assert validate_limit(None) == 50


@pytest.mark.parametrize("limit", [1, 50, 100])
def test_validate_limit_ok(limit: int) -> None:
    assert validate_limit(limit) == limit


@pytest.mark.parametrize("limit", [0, -1, 101])
def test_validate_limit_invalid(limit: int) -> None:
    with pytest.raises(ValidationError):
        validate_limit(limit)


def test_first_page() -> None:
    page = paginate_newest_first(ITEMS, None, 3)
    assert [item["id"] for item in page] == [10, 9, 8]


def test_page_after_cursor() -> None:
    page = paginate_newest_first(ITEMS, 8, 3)
    assert [item["id"] for item in page] == [7, 6]


def test_cursor_not_found_raises() -> None:
    with pytest.raises(ValidationError):
        paginate_newest_first(ITEMS, 999, 3)


def test_tail_page() -> None:
    page = paginate_newest_first(ITEMS, 7, 3)
    assert [item["id"] for item in page] == [6]
