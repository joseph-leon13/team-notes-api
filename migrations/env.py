"""Alembic environment: migrates the database named by the application's settings.

The URL comes from ``team_notes_api.core.config.get_settings().database_url`` (i.e. the
``NOTES_DATABASE_URL`` environment variable or ``.env``), never from ``alembic.ini``,
so the app and its migrations can't point at different databases.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from team_notes_api import models  # noqa: F401  (registers every table on Base.metadata)
from team_notes_api.core.config import Settings
from team_notes_api.core.db import Base

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logging", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    """Read the URL fresh from settings (uncached, so tests can point it at a temp DB)."""
    return Settings().database_url


def _configure_kwargs(url: str) -> dict:
    """Options shared by offline and online runs."""
    return {
        "target_metadata": target_metadata,
        "compare_type": True,
        # SQLite can't ALTER most constraints; batch mode recreates the table instead.
        "render_as_batch": url.startswith("sqlite"),
    }


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting (``alembic upgrade head --sql``)."""
    url = _database_url()
    context.configure(
        url=url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **_configure_kwargs(url),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect to the database and apply migrations."""
    url = _database_url()
    connectable = engine_from_config(
        {"sqlalchemy.url": url}, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, **_configure_kwargs(url))
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
