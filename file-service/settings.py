from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    storage_path: str
    cleanup_api_key: str


    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()