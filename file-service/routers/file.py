import json

from typing import List, Optional
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, UploadFile, File, Header, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from settings import settings
from infrastructure.data.database import SessionLocal
from infrastructure.security.dependencies import get_current_user
from infrastructure.di.providers import (
    get_start_upload_uc,
    get_upload_chunk_uc,
    get_delete_file_by_session_uc,
    get_files_metadata_batch_uc,
    get_thumbnail_uc,
    get_commit_file_uc,
    get_download_file_uc,
    get_delete_file_by_session_cleanup_uc,
)
from core.errors.file_error_mapper import map_channel_error

from schemas.start_upload_schema import StartUploadResponse
from schemas.upload_chunk_schema import UploadChunkRequest, UploadChunkResponse
from schemas.get_files_metadata_schema import GetFilesMetadataRequest, FileMetadataResponse


router = APIRouter()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


@router.post("/upload/start", response_model=StartUploadResponse)
async def start_upload(_user=Depends(get_current_user)):
    try:
        uc = await get_start_upload_uc()
        session_id = await uc.execute(public_id=_user["public_id"])
        return StartUploadResponse(session_id=session_id)
    except Exception as exc:
        raise map_channel_error(exc)


@router.post("/upload/chunk", response_model=UploadChunkResponse)
async def upload_chunk(
    payload: UploadChunkRequest = Depends(),
    chunk: UploadFile = File(...),
    _user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        uc = await get_upload_chunk_uc(session)
        result = await uc.execute(
            session_id=payload.session_id,
            public_id=_user["public_id"],
            chunk=await chunk.read(),
            chunk_number=payload.chunk_number,
            total_chunks=payload.total_chunks,
            is_private=payload.is_private,
            is_protect=payload.is_protect,
            resize=json.loads(payload.resize) if payload.resize else None,
            name=payload.name,
        )
        return UploadChunkResponse(**result)
    except Exception as exc:
        raise map_channel_error(exc)


@router.post("/internal/cleanup/{session_id}")
async def cleanup_file(
    session_id: str,
    x_api_key: str = Header(None),
    session: AsyncSession = Depends(get_session),
):
    if x_api_key != settings.cleanup_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        uc = get_delete_file_by_session_uc(session)
        await uc.execute(session_id)
        return {"status": "ok"}
    except Exception as exc:
        raise map_channel_error(exc)


@router.post("/metadata", response_model=List[FileMetadataResponse])
async def get_files_metadata(
    payload: GetFilesMetadataRequest,
    session: AsyncSession = Depends(get_session),
    _user=Depends(get_current_user),
):
    try:
        uc = await get_files_metadata_batch_uc(session)
        result = await uc.execute(payload.lookup_keys)
        return [FileMetadataResponse(**r.__dict__) for r in result]
    except Exception as exc:
        raise map_channel_error(exc)


@router.get("/thumbnail/{session_id}")
async def get_thumbnail(session_id: str, _user=Depends(get_current_user)):
    try:
        uc = get_thumbnail_uc()
        thumbnail_bytes = await uc.execute(session_id)
        if not thumbnail_bytes:
            raise HTTPException(status_code=404, detail="Thumbnail not found")
        return Response(content=thumbnail_bytes, media_type="image/jpeg")
    except Exception as exc:
        raise map_channel_error(exc)


@router.post("/commit/{lookup_key}")
async def commit_file(
    lookup_key: str,
    session: AsyncSession = Depends(get_session),
    _user=Depends(get_current_user),
):
    try:
        uc = get_commit_file_uc(session)
        await uc.execute(lookup_key)
        return {"status": "committed", "lookup_key": lookup_key}
    except Exception as exc:
        raise map_channel_error(exc)


@router.get("/download/{lookup_key}")
async def download_file(
    lookup_key: str,
    chunk_number: int,
    signature: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    _user=Depends(get_current_user),
):
    try:
        uc = await get_download_file_uc(session)
        chunk_bytes = await uc.execute(
            lookup_key=lookup_key,
            chunk_number=chunk_number,
            signature=signature,
            public_id=_user["public_id"]
        )
        return Response(content=chunk_bytes, media_type="application/octet-stream")
    except Exception as exc:
        raise map_channel_error(exc)

@router.post("/internal/cleanup/file/{session_id}")
async def cleanup_file_by_session(
    session_id: str,
    x_api_key: str = Header(None),
    session: AsyncSession = Depends(get_session),
):
    if x_api_key != settings.cleanup_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        uc = get_delete_file_by_session_cleanup_uc(session)
        await uc.execute(session_id)
        return {"status": "ok"}
    except Exception as exc:
        raise map_channel_error(exc)
