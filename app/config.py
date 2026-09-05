from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://fx_api:fx_api@localhost:5432/fx_api"
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
