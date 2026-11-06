from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Messenger"
    debug: bool = False
    database_url: str = "postgresql+asyncpg://messenger:messenger@localhost:5432/messenger"
    db_pool_size: int = 10
    db_max_overflow: int = 5
    db_pool_timeout_seconds: int = 10
    media_root: Path = Path("./data/media")
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 30
    otp_ttl_seconds: int = 300
    otp_length: int = 6
    registration_token_ttl_minutes: int = 10
    max_artifact_size_mb: int = 20

    redis_url: str | None = "redis://localhost:6379/0"
    upload_consumer_enabled: bool = True
    consumer_db_pool_size: int = 2
    upload_ticket_secret: str = "dev-upload-ticket-secret-change-me-0123456789"
    upload_ticket_issuer: str = "messenger-backend"
    upload_ticket_audience: str = "file-service"
    upload_ticket_ttl_seconds: int = 3600
    upload_event_max_age_seconds: int = 6 * 3600
    file_service_upload_url: str = "/files/v1/uploads"
    completed_stream: str = "upload.completed"
    outcome_stream: str = "upload.outcome"
    upload_consumer_group: str = "messenger-backend"
    stream_maxlen: int = 100_000
    stream_block_ms: int = 5000
    stream_max_deliveries: int = 5
    stream_claim_min_idle_ms: int = 60_000
    stream_claim_interval_seconds: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
