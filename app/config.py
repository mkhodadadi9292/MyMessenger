from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Messenger"
    debug: bool = False
    database_url: str = "sqlite+aiosqlite:///./data/messenger.db"
    media_root: Path = Path("./data/media")
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 30
    otp_ttl_seconds: int = 300
    otp_length: int = 6
    max_artifact_size_mb: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
