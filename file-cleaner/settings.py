from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    cleanup_api_key:str
    redis_url: str
    kafka_url: str
    database_url: str
    file_service_url: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()