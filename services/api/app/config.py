"""Settings, read from environment variables (or a .env file)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="CARTSENSE_", extra="ignore")

    # SQLite works for local development and tests; production uses PostgreSQL,
    # e.g. postgresql+psycopg://user:pass@host:5432/cartsense
    database_url: str = "sqlite:///./cartsense.db"
    jwt_secret: str = "change-me-in-production"
    jwt_expiry_hours: int = 24 * 7
    cors_origins: str = "http://localhost:3000"
    export_dir: Path = Path("../../artifacts/export")
    # Product images are hosted by Amazon; they are not shown unless enabled
    show_product_images: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
