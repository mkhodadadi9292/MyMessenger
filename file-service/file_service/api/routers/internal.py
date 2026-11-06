from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from file_service.api.deps import get_cleanup_service, require_internal_key
from file_service.application.cleanup_service import CleanupRule, CleanupService

router = APIRouter(
    prefix="/internal/v1", tags=["internal"], dependencies=[Depends(require_internal_key)]
)


class CleanupIn(BaseModel):
    older_than_seconds: int = Field(ge=0)
    limit: int = Field(default=100, ge=1, le=1000)


class CleanupOut(BaseModel):
    rule: str
    purged: list[str]
    skipped: list[str]


@router.post("/cleanup/{rule}", response_model=CleanupOut)
async def run_cleanup(
    rule: CleanupRule, body: CleanupIn, service: CleanupService = Depends(get_cleanup_service)
) -> CleanupOut:
    return CleanupOut(**await service.run(rule, body.older_than_seconds, body.limit))
