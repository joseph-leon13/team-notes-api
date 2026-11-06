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
    # Browser origins allowed to call the API, comma-separated (e.g.
    # "https://notes.example.com,http://localhost:5173"). Empty means no cross-origin
    # access, which is the safe default for an API without a front-end yet.
    cors_origins: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        """Return the configured CORS origins as a clean list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings (cached; tests override via dependency injection)."""
    return Settings()
