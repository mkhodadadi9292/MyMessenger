class DomainError(Exception):
    """Base for all domain-level errors, mapped to HTTP in api/errors.py."""


class ValidationError(DomainError):
    pass


class UnauthorizedError(DomainError):
    pass


class ForbiddenError(DomainError):
    pass


class NotMemberError(ForbiddenError):
    pass


class BlockedError(ForbiddenError):
    pass


class NotFoundError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class DuplicateUploadError(ConflictError):
    pass
