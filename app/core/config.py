from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Link Analytics Platform"
    environment: str = "development"
    debug: bool = True

    database_url: str = "sqlite:///./app.db"
    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl: int = 86400

    redis_stream_name: str = "clicks:stream"
    redis_consumer_group: str = "analytics_group"
    consumer_batch_size: int = 100
    consumer_block_ms: int = 2000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()