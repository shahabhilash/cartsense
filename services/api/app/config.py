"""Settings, read from environment variables (or a .env file)."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(url: str) -> str:
    """Accept database URLs exactly as hosting providers show them.

    Render and Railway give ``postgres://`` or ``postgresql://`` URLs, which
    SQLAlchemy would try to open with the psycopg2 driver. This project
    uses psycopg 3, so the scheme is rewritten to ``postgresql+psycopg://``.
    Stray quotes and whitespace from copy-pasting are removed as well.
    """
    url = url.strip().strip("'\"").strip()
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def redact_database_url(url: str) -> str:
    """The URL with its password replaced, safe to write to logs."""
    scheme, sep, rest = url.partition("://")
    if not sep or "@" not in rest:
        return url
    credentials, host = rest.rsplit("@", 1)
    user = credentials.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host}"


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
    # A/B test: share of visitors who get the popularity control (0 turns the test off)
    ab_control_share: float = 0.0
    ab_experiment: str = "hybrid-vs-popular"

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @property
    def cors_origin_list(self) -> list[str]:
        # Browsers send the origin without a trailing slash or quotes, so a
        # value pasted as "https://shop.example.com/" must still match
        origins = (o.strip().strip("'\"").rstrip("/") for o in self.cors_origins.split(","))
        return [o for o in origins if o]


@lru_cache
def get_settings() -> Settings:
    return Settings()
