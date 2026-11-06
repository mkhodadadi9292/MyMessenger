from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "file-service"
    database_url: str = "postgresql+asyncpg://file_service:file_service@localhost:5432/file_service"
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_pool_timeout_seconds: int = 10
    redis_url: str | None = "redis://localhost:6379/0"
    workers_enabled: bool = True

    media_root: Path = Path("./data/media")
    chunks_root: Path = Path("./data/uploads")
    upload_chunk_size_bytes: int = 1024 * 1024
    max_upload_size_bytes: int = 20 * 1024 * 1024

    upload_ticket_secret: str = "dev-upload-ticket-secret-change-me-0123456789"
    upload_ticket_issuer: str = "messenger-backend"
    upload_ticket_audience: str = "file-service"
    internal_api_key: str = "dev-internal-api-key-change-me"

    completed_stream: str = "upload.completed"
    outcome_stream: str = "upload.outcome"
    outcome_group: str = "file-service"
    backend_group: str = "messenger-backend"
    stream_maxlen: int = 100_000
    stream_block_ms: int = 5000
    stream_max_deliveries: int = 5
    stream_claim_min_idle_ms: int = 60_000
    stream_claim_interval_seconds: int = 30
    outbox_relay_interval_seconds: int = 10
    outbox_min_age_seconds: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
