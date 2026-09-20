from app.api.errors import status_for
from app.domain.exceptions import (
    ConflictError,
    DomainError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)


def test_status_mapping() -> None:
    assert status_for(ValidationError("x")) == 400
    assert status_for(UnauthorizedError("x")) == 401
    assert status_for(ForbiddenError("x")) == 403
    assert status_for(NotFoundError("x")) == 404
    assert status_for(ConflictError("x")) == 409
    assert status_for(DomainError("x")) == 500


def test_subclass_uses_parent_status() -> None:
    class CustomNotFound(NotFoundError):
        pass

    assert status_for(CustomNotFound("x")) == 404
