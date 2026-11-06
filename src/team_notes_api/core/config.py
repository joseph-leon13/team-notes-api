"""Application settings, read from environment variables (prefix ``NOTES_``)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration.

    ``database_url`` is the only switch needed to move storage: SQLite by default,
    any SQLAlchemy URL (e.g. ``postgresql+psycopg://...``) otherwise.
    """

    model_config = SettingsConfigDict(env_prefix="NOTES_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./notes.db"
    default_page_size: int = 20
    max_page_size: int = 100


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings (cached; tests override via dependency injection)."""
    return Settings()
