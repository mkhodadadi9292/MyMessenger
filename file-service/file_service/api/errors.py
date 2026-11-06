from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from file_service.domain.exceptions import (
    ConflictError,
    DomainError,
    LengthRequiredError,
    MissingChunksError,
    NotFoundError,
    PayloadTooLargeError,
    UnauthorizedError,
    ValidationError,
    VerificationError,
)

_STATUS_BY_ERROR: dict[type[DomainError], int] = {
    ValidationError: 400,
    UnauthorizedError: 401,
    NotFoundError: 404,
    ConflictError: 409,
    LengthRequiredError: 411,
    PayloadTooLargeError: 413,
    VerificationError: 422,
}


def status_for(exc: DomainError) -> int:
    for cls in type(exc).__mro__:
        if cls in _STATUS_BY_ERROR:
            return _STATUS_BY_ERROR[cls]
    return 500


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        body: dict = {"detail": str(exc)}
        if isinstance(exc, MissingChunksError):
            body["missing_chunks"] = exc.missing_chunks
        headers = {"WWW-Authenticate": "Bearer"} if isinstance(exc, UnauthorizedError) else None
        return JSONResponse(status_code=status_for(exc), content=body, headers=headers)
