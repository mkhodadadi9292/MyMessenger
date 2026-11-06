from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from infrastructure.data.database import engine, SessionLocal
from infrastructure.data.model.models import Base
from infrastructure.redis.redis_client import RedisClient
from infrastructure.redis.session_expire_listener import SessionExpireListener
from infrastructure.redis.delete_file_stream_worker import build_delete_file_stream_worker
from infrastructure.redis.update_file_protect_stream_worker import build_update_file_protect_stream_worker
from infrastructure.di.providers import get_delete_file_by_session_uc
from infrastructure.logging.logger import logger

from routers import file as file_router


redis_client = RedisClient()


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as conn:  # type: ignore
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized.")

    client = await redis_client.get_client()

    async with SessionLocal() as session:
        delete_uc = get_delete_file_by_session_uc(session)
        expire_listener = SessionExpireListener(client, delete_uc)
        asyncio.create_task(expire_listener.start())
        logger.info("SessionExpireListener started.")

    workers = [
        build_delete_file_stream_worker(),
        build_update_file_protect_stream_worker(),
    ]
    for worker in workers:
        asyncio.create_task(worker.run())
        logger.info(f"{worker.consumer_name} started.")

    try:
        yield
    finally:
        logger.info("File Service shutting down...")


app = FastAPI(
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(file_router.router, tags=["file"])