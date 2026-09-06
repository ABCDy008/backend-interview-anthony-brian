from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Configure database, business timezone, and home-currency settings."""

    database_url: str = "postgresql+psycopg://fx_api:fx_api@localhost:5432/fx_api"
    home_currency: str = "PHP"
    business_timezone: str = "Asia/Manila"
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings instance."""
    return Settings()
