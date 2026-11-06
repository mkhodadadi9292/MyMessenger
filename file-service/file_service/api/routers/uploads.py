from fastapi import APIRouter, Depends, Path, Request, Response
from pydantic import BaseModel

from file_service.api.deps import get_ticket, get_upload_service
from file_service.application.upload_service import UploadService, UploadState

router = APIRouter(prefix="/files/v1/uploads", tags=["uploads"])

UploadIdPath = Path(pattern=r"^[0-9a-f]{32}$")


class UploadStateOut(BaseModel):
    upload_id: str
    status: str
    chunk_size: int
    total_chunks: int
    size_bytes: int
    received_chunks: list[int]


class ChunkOut(BaseModel):
    upload_id: str
    index: int
    size_bytes: int


def state_to_out(state: UploadState) -> UploadStateOut:
    session = state.session
    return UploadStateOut(
        upload_id=session.upload_id,
        status=session.status.value,
        chunk_size=session.chunk_size,
        total_chunks=session.total_chunks,
        size_bytes=session.size_bytes,
        received_chunks=state.received_chunks,
    )


@router.post("", response_model=UploadStateOut)
async def init_upload(
    response: Response,
    ticket: str = Depends(get_ticket),
    service: UploadService = Depends(get_upload_service),
) -> UploadStateOut:
    state, created = await service.init(ticket)
    response.status_code = 201 if created else 200
    return state_to_out(state)


@router.put("/{upload_id}/chunks/{index}", response_model=ChunkOut)
async def put_chunk(
    request: Request,
    index: int,
    upload_id: str = UploadIdPath,
    ticket: str = Depends(get_ticket),
    service: UploadService = Depends(get_upload_service),
) -> ChunkOut:
    raw_length = request.headers.get("content-length")
    content_length = int(raw_length) if raw_length and raw_length.isdigit() else None
    size = await service.put_chunk(ticket, upload_id, index, content_length, request.stream())
    return ChunkOut(upload_id=upload_id, index=index, size_bytes=size)


@router.get("/{upload_id}", response_model=UploadStateOut)
async def get_upload(
    upload_id: str = UploadIdPath,
    ticket: str = Depends(get_ticket),
    service: UploadService = Depends(get_upload_service),
) -> UploadStateOut:
    return state_to_out(await service.status(ticket, upload_id))


@router.post("/{upload_id}/complete", status_code=202, response_model=UploadStateOut)
async def complete_upload(
    upload_id: str = UploadIdPath,
    ticket: str = Depends(get_ticket),
    service: UploadService = Depends(get_upload_service),
) -> UploadStateOut:
    return state_to_out(await service.complete(ticket, upload_id))


@router.delete("/{upload_id}", status_code=204)
async def abort_upload(
    upload_id: str = UploadIdPath,
    ticket: str = Depends(get_ticket),
    service: UploadService = Depends(get_upload_service),
) -> Response:
    await service.abort(ticket, upload_id)
    return Response(status_code=204)
