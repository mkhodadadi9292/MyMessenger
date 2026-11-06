class DomainError(Exception):
    pass


class ValidationError(DomainError):
    pass


class UnauthorizedError(DomainError):
    pass


class NotFoundError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class MissingChunksError(ConflictError):
    def __init__(self, missing_chunks: list[int]) -> None:
        super().__init__("upload is missing chunks")
        self.missing_chunks = missing_chunks


class LengthRequiredError(DomainError):
    pass


class PayloadTooLargeError(DomainError):
    pass


class VerificationError(DomainError):
    pass
